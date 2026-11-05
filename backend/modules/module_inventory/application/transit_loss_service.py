"""Historical dispatch value release, using the existing writer/ledger engine."""
from decimal import Decimal, localcontext, ROUND_HALF_UP
from fastapi import HTTPException
from .transfer_service import TransferPosting
from .inventory_service import InventoryService
from .posting_access import warehouse
from ..domain.financial_policy import Valuation, quantity, money, COST_SCALE, transfer_allocation


class TransitLossPosting(TransferPosting):
    async def apply(self, doc, lines, entity, at):
        if not doc.get('reason') or not doc['reason'].strip():
            raise HTTPException(422,'LOSS_REASON_REQUIRED')
        destination=await warehouse(self.session,self.request,doc['destination_warehouse_id'],'inventory.documents.post')
        owner=await self.repo.one('SELECT * FROM inv_warehouse_owners WHERE warehouse_id=:w',w=destination['id'])
        if destination['organization_id']!=doc['organization_id'] or not owner or owner['legal_entity_id']!=entity['id']:
            raise HTTPException(409,'TRANSFER_OWNER_SCOPE_MISMATCH')
        service=InventoryService(self.session,self.request)
        for line in lines:
            original=await self.repo.one('SELECT l.*,d.document_type,d.status,d.organization_id,d.legal_entity_id,d.warehouse_id,d.destination_warehouse_id '
                'FROM inv_document_lines l JOIN inv_effective_documents d ON d.id=l.document_id WHERE l.id=:i',i=line['dispatch_line_id'])
            if not original or original['status'] not in ('POSTED','CLOSED') or original['document_type']!='TRANSFER_DISPATCH':
                raise HTTPException(409,'POSTED_DISPATCH_REQUIRED')
            if any(original[k]!=doc[k] for k in ('organization_id','warehouse_id','destination_warehouse_id')) or original['legal_entity_id']!=entity['id'] or any(original[k]!=line[k] for k in ('item_id','location_id','destination_location_id')):
                raise HTTPException(422,'TRANSFER_DISPATCH_SCOPE_MISMATCH')
            item=await service._reference('inv_items',line['item_id'])
            if item['organization_id']!=doc['organization_id'] or item['tracking_policy']!='none':
                raise HTTPException(422,'TRANSFER_ITEM_INELIGIBLE')
            unit=await service._reference('inv_units',item['base_unit_id'])
            q=quantity(line['base_quantity'],unit['precision'])
            previous=await self.repo.many("SELECT l.base_quantity,l.amount_valuation FROM inv_document_lines l JOIN inv_effective_documents d ON d.id=l.document_id "
                "WHERE l.dispatch_line_id=:i AND d.document_type IN ('TRANSFER_RECEIPT','LOSS_TRANSIT') AND (d.status IN ('POSTED','CLOSED') OR (d.id=:current AND l.line_no<:n))",
                i=original['id'],current=doc['id'],n=line['line_no'])
            settled=sum((Decimal(r['base_quantity']) for r in previous),Decimal(0))
            remaining=Decimal(original['base_quantity'])-settled
            if q>remaining:
                raise HTTPException(409,'TRANSFER_OVER_SETTLEMENT')
            value=transfer_allocation(original['base_quantity'],original['amount_valuation'],settled,
                sum((Decimal(r['amount_valuation']) for r in previous),Decimal(0)),q)
            with localcontext() as ctx:
                ctx.prec=50
                cost=(value/q).quantize(COST_SCALE,rounding=ROUND_HALF_UP)
            valuation=await self.repo.one('SELECT * FROM inv_valuation_state WHERE legal_entity_id=:l AND item_id=:i AND valuation_currency_id=:c',
                l=entity['id'],i=item['id'],c=entity['valuation_currency_id'])
            if not valuation:
                raise HTTPException(409,'VALUATION_UNAVAILABLE')
            before=Valuation(Decimal(valuation['quantity_total']),Decimal(valuation['inventory_value']),Decimal(valuation['avg_cost']))
            before._validate()
            with localcontext() as ctx:
                ctx.prec=50
                after_q=before.quantity_total-q
                after_value=money(before.inventory_value-value)
                if after_q<0 or after_value<0 or (not after_q and after_value):
                    raise HTTPException(409,'LOSS_REQUIRES_VALUATION_CORRECTION')
                after=Valuation(after_q,after_value,(after_value/after_q).quantize(COST_SCALE,rounding=ROUND_HALF_UP) if after_q else Decimal(0))
            after._validate()
            source=await self.balance(doc,entity,item['id'],doc['warehouse_id'],line['location_id'],'IN_TRANSIT')
            if not source or Decimal(source['quantity_on_hand'])<q:
                raise HTTPException(409,'INSUFFICIENT_TRANSIT_STOCK')
            await self.repo.update('inv_document_lines',line['id'],{'valuation_currency_id':entity['valuation_currency_id'],
                'unit_cost_valuation':str(cost),'amount_valuation':str(value)})
            await self.leg(doc,line,entity,at,source,doc['warehouse_id'],line['location_id'],'IN_TRANSIT',-q,-value,before.avg_cost,'LOSS',new_average=after.avg_cost)
            # The shared leg writer records location snapshots; loss also changes the valuation scope.
            await self.repo.update('inv_valuation_state',valuation['id'],{'quantity_total':str(after.quantity_total),
                'inventory_value':str(after.inventory_value),'avg_cost':str(after.avg_cost),'version':valuation['version']+1})
