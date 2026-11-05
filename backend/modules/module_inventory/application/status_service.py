"""Controlled classification and disposal in the existing posting transaction."""
from decimal import Decimal, localcontext, ROUND_HALF_UP
from fastapi import HTTPException
from .transfer_service import TransferPosting
from .inventory_service import InventoryService
from .reservation_service import ReservationService
from ..domain.financial_policy import Valuation, quantity, COST_SCALE


class StatusPosting(TransferPosting):
    async def apply(self,doc,lines,entity,at):
        source_status=doc['source_stock_status']
        target_status=doc['target_stock_status']
        scrap=doc['document_type']=='SCRAP'
        if source_status not in ('AVAILABLE','QUARANTINE','DAMAGED') or not (doc.get('reason') or '').strip():
            raise HTTPException(422,'STATUS_AND_REASON_REQUIRED')
        if (scrap and (source_status=='AVAILABLE' or target_status)) or (not scrap and (target_status not in ('AVAILABLE','QUARANTINE','DAMAGED') or target_status==source_status)):
            raise HTTPException(422,'INVALID_STOCK_STATUS_TRANSITION')
        if doc.get('source_module') or doc.get('destination_warehouse_id'):
            raise HTTPException(422,'STATUS_EXTERNAL_REFERENCE_FORBIDDEN')
        service=InventoryService(self.session,self.request)
        for line in lines:
            if any(line.get(k) for k in ('request_line_id','origin_line_id','dispatch_line_id','destination_location_id')):
                raise HTTPException(422,'STATUS_LINE_REFERENCE_FORBIDDEN')
            item=await service._reference('inv_items',line['item_id'])
            if item['organization_id']!=doc['organization_id'] or item['tracking_policy']!='none':
                raise HTTPException(422,'STATUS_ITEM_SCOPE_MISMATCH')
            unit=await service._reference('inv_units',item['base_unit_id'])
            q=quantity(line['base_quantity'],unit['precision'])
            if line['location_id']:
                loc=await service._reference('inv_locations',line['location_id'])
                if loc['warehouse_id']!=doc['warehouse_id']:
                    raise HTTPException(422,'STATUS_LOCATION_SCOPE_MISMATCH')
            source=await self.balance(doc,entity,item['id'],doc['warehouse_id'],line['location_id'],source_status)
            on_hand=Decimal(source['quantity_on_hand']) if source else Decimal(0)
            if q>on_hand:
                raise HTTPException(409,'INSUFFICIENT_STATUS_STOCK')
            if source_status=='AVAILABLE':
                reserved=ReservationService.amount(await ReservationService(self.session,self.request).outstanding(doc['warehouse_id'],item['id'],line['location_id']))
                if q>on_hand-reserved:
                    raise HTTPException(409,'INSUFFICIENT_UNRESERVED_STOCK')
            valuation=await self.repo.one('SELECT * FROM inv_valuation_state WHERE legal_entity_id=:l AND item_id=:i AND valuation_currency_id=:c',l=entity['id'],i=item['id'],c=entity['valuation_currency_id'])
            if not valuation:
                raise HTTPException(409,'VALUATION_UNAVAILABLE')
            before=Valuation(Decimal(valuation['quantity_total']),Decimal(valuation['inventory_value']),Decimal(valuation['avg_cost']))
            after,value=before.issue(q)
            with localcontext() as ctx:
                ctx.prec=50
                cost=(value/q).quantize(COST_SCALE,rounding=ROUND_HALF_UP)
            await self.repo.update('inv_document_lines',line['id'],{'valuation_currency_id':entity['valuation_currency_id'],'unit_cost_valuation':str(cost),'amount_valuation':str(value)})
            await self.leg(doc,line,entity,at,source,doc['warehouse_id'],line['location_id'],source_status,-q,-value,before.avg_cost,'SOURCE',new_average=after.avg_cost if scrap else before.avg_cost)
            if scrap:
                await self.repo.update('inv_valuation_state',valuation['id'],{'quantity_total':str(after.quantity_total),'inventory_value':str(after.inventory_value),'avg_cost':str(after.avg_cost),'version':valuation['version']+1})
            else:
                target=await self.balance(doc,entity,item['id'],doc['warehouse_id'],line['location_id'],target_status)
                await self.leg(doc,line,entity,at,target,doc['warehouse_id'],line['location_id'],target_status,q,value,before.avg_cost,'DESTINATION')
