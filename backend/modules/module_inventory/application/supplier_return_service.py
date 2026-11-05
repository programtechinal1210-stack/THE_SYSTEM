"""Bounded historical receipt settlement, never a current-WAC substitute."""
from collections import defaultdict
from decimal import Decimal,localcontext,ROUND_HALF_UP
from fastapi import HTTPException
from .transfer_service import TransferPosting
from .posting_access import warehouse
from .reservation_service import ReservationService
from ..domain.financial_policy import Valuation,quantity,money,transfer_allocation,COST_SCALE


class SupplierReturnPosting(TransferPosting):
    async def origin(self,organization_id,warehouse_id,item_id,origin_id):
        await warehouse(self.session,self.request,warehouse_id,'inventory.documents.view')
        row=await self.repo.one('SELECT l.*,d.organization_id,d.warehouse_id,d.legal_entity_id,d.document_type,d.status '
            'FROM inv_document_lines l JOIN inv_effective_documents d ON d.id=l.document_id WHERE l.id=:i',i=origin_id)
        if not row or row['document_type']!='RECEIPT' or row['status'] not in ('POSTED','CLOSED'):
            raise HTTPException(409,'POSTED_RECEIPT_REQUIRED')
        if row['organization_id']!=organization_id or row['warehouse_id']!=warehouse_id or row['item_id']!=item_id:
            raise HTTPException(422,'SUPPLIER_RETURN_ORIGIN_SCOPE_MISMATCH')
        return row

    async def apply(self,doc,lines,entity,at):
        from .inventory_service import InventoryService
        if not (doc.get('counterparty_reference') or '').strip() or not (doc.get('reason') or '').strip() or doc.get('source_module'):
            raise HTTPException(422,'SUPPLIER_REFERENCE_AND_REASON_REQUIRED')
        service=InventoryService(self.session,self.request)
        for line in lines:
            if any(line.get(k) for k in ('request_line_id','dispatch_line_id','destination_location_id')):
                raise HTTPException(422,'SUPPLIER_RETURN_REFERENCE_FORBIDDEN')
            original=await self.origin(doc['organization_id'],doc['warehouse_id'],line['item_id'],line['origin_line_id'])
            if original['legal_entity_id']!=entity['id'] or original['valuation_currency_id']!=entity['valuation_currency_id']:
                raise HTTPException(422,'SUPPLIER_RETURN_OWNER_MISMATCH')
            item=await service._reference('inv_items',line['item_id'])
            if item['organization_id']!=doc['organization_id'] or item['tracking_policy']!='none':
                raise HTTPException(422,'SUPPLIER_RETURN_ITEM_INELIGIBLE')
            unit=await service._reference('inv_units',item['base_unit_id']);q=quantity(line['base_quantity'],unit['precision'])
            if line['location_id']:
                loc=await service._reference('inv_locations',line['location_id'])
                if loc['warehouse_id']!=doc['warehouse_id']:
                    raise HTTPException(422,'SUPPLIER_RETURN_LOCATION_MISMATCH')
            previous=await self.repo.many("SELECT l.base_quantity,l.amount_valuation,l.original_amount FROM inv_document_lines l JOIN inv_effective_documents d ON d.id=l.document_id "
                "WHERE l.origin_line_id=:i AND d.document_type='RETURN_SUPPLIER' AND (d.status IN ('POSTED','CLOSED') OR (d.id=:current AND l.line_no<:n))",i=original['id'],current=doc['id'],n=line['line_no'])
            used=sum((Decimal(r['base_quantity']) for r in previous),Decimal(0))
            if used+q>Decimal(original['base_quantity']):
                raise HTTPException(409,'SUPPLIER_RETURN_QUANTITY_EXCEEDED')
            if any(original[k] is None for k in ('original_amount','amount_valuation','transaction_currency_id','fx_rate')):
                raise HTTPException(409,'RECEIPT_FINANCIAL_SNAPSHOT_REQUIRED')
            value=transfer_allocation(original['base_quantity'],original['amount_valuation'],used,sum((Decimal(r['amount_valuation']) for r in previous),Decimal(0)),q)
            original_value=transfer_allocation(original['base_quantity'],original['original_amount'],used,sum((Decimal(r['original_amount']) for r in previous),Decimal(0)),q)
            source=await self.balance(doc,entity,item['id'],doc['warehouse_id'],line['location_id'],'AVAILABLE')
            on_hand=Decimal(source['quantity_on_hand']) if source else Decimal(0)
            reserved=ReservationService.amount(await ReservationService(self.session,self.request).outstanding(doc['warehouse_id'],item['id'],line['location_id']))
            if q>on_hand-reserved:
                raise HTTPException(409,'INSUFFICIENT_UNRESERVED_STOCK')
            state=await self.repo.one('SELECT * FROM inv_valuation_state WHERE legal_entity_id=:l AND item_id=:i AND valuation_currency_id=:c',l=entity['id'],i=item['id'],c=entity['valuation_currency_id'])
            if not state:
                raise HTTPException(409,'VALUATION_UNAVAILABLE')
            before=Valuation(Decimal(state['quantity_total']),Decimal(state['inventory_value']),Decimal(state['avg_cost']))
            before._validate()
            if q>before.quantity_total:
                raise HTTPException(409,'INSUFFICIENT_STOCK')
            with localcontext() as ctx:
                ctx.prec=50
                remaining_q=before.quantity_total-q;remaining_value=money(before.inventory_value-value)
                if remaining_value<0 or (not remaining_q and remaining_value):
                    raise HTTPException(409,'HISTORICAL_RETURN_REQUIRES_VALUATION_CORRECTION')
                average=(remaining_value/remaining_q).quantize(COST_SCALE,rounding=ROUND_HALF_UP) if remaining_q else Decimal(0)
                cost=(value/q).quantize(COST_SCALE,rounding=ROUND_HALF_UP)
                input_price=(original_value/Decimal(line['quantity'])).quantize(COST_SCALE,rounding=ROUND_HALF_UP)
            Valuation(remaining_q,remaining_value,average)._validate()
            financial={k:original[k] for k in ('transaction_currency_id','valuation_currency_id','fx_rate','fx_effective_at','fx_source_ref')}
            financial.update(original_amount=str(original_value),original_unit_price=str(input_price),amount_valuation=str(value),unit_cost_valuation=str(cost))
            await self.repo.update('inv_document_lines',line['id'],financial)
            await self.leg(doc,line,entity,at,source,doc['warehouse_id'],line['location_id'],'AVAILABLE',-q,-value,before.avg_cost,'SOURCE',new_average=average)
            await self.repo.update('inv_valuation_state',state['id'],{'quantity_total':str(remaining_q),'inventory_value':str(remaining_value),'avg_cost':str(average),'version':state['version']+1})

    async def references(self,warehouse_id):
        await warehouse(self.session,self.request,warehouse_id,'inventory.documents.create')
        await warehouse(self.session,self.request,warehouse_id,'inventory.documents.view')
        rows=await self.repo.many("SELECT l.id,l.item_id,l.location_id,l.base_quantity,d.document_no FROM inv_document_lines l JOIN inv_effective_documents d ON d.id=l.document_id WHERE d.warehouse_id=:w AND d.document_type='RECEIPT' AND d.status IN ('POSTED','CLOSED') ORDER BY d.posted_at DESC,l.id LIMIT 200",w=warehouse_id)
        if not rows:return {'items':[]}
        bindings={f'i{n}':r['id'] for n,r in enumerate(rows)};ids=','.join(':'+k for k in bindings)
        settled=await self.repo.many("SELECT l.origin_line_id,l.base_quantity FROM inv_document_lines l JOIN inv_effective_documents d ON d.id=l.document_id WHERE d.document_type='RETURN_SUPPLIER' AND d.status IN ('POSTED','CLOSED') AND l.origin_line_id IN ("+ids+")",**bindings)
        quantities=defaultdict(Decimal)
        for r in settled:quantities[r['origin_line_id']]+=Decimal(r['base_quantity'])
        result=[]
        for r in rows:
            remaining=Decimal(r['base_quantity'])-quantities[r['id']]
            if remaining>0:result.append({**r,'remaining_receipt_quantity':str(remaining)})
        return {'items':result}
