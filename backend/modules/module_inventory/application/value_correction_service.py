"""Separately approved value corrections never rewrite historical quantities/costs."""
from decimal import Decimal,localcontext,ROUND_HALF_UP
from fastapi import HTTPException
from core.access import require
from .posting_access import warehouse,costs
from .transfer_service import TransferPosting
from ..domain.financial_policy import Valuation,decimal,money,COST_SCALE


def authorize(request,organization_id):
    permission='inventory.valuation.correct'
    require(request,permission)
    if not request.state.is_admin and 'institution' not in request.state.permission_global_scopes.get(permission,set()):
        raise HTTPException(403,'VALUATION_CORRECTION_REQUIRES_INSTITUTION_SCOPE')
    if not costs(request,organization_id):
        raise HTTPException(403,'VALUATION_CORRECTION_REQUIRES_COST_VISIBILITY')


class ValueCorrectionPosting(TransferPosting):
    async def authorize_document_sources(self,doc):
        authorize(self.request,doc['organization_id'])
        parents=await self.repo.many('SELECT DISTINCT d.warehouse_id,d.destination_warehouse_id FROM inv_document_lines l '
            'JOIN inv_document_lines original ON original.id=l.origin_line_id JOIN inv_documents d ON d.id=original.document_id WHERE l.document_id=:i',i=doc['id'])
        identifiers={p[k] for p in parents for k in ('warehouse_id','destination_warehouse_id') if p[k]}
        for identifier in identifiers:
            await warehouse(self.session,self.request,identifier,'inventory.documents.view')

    async def origin(self,organization_id,warehouse_id,item_id,origin_id):
        await warehouse(self.session,self.request,warehouse_id,'inventory.documents.view')
        row=await self.repo.one('SELECT l.*,d.organization_id,d.warehouse_id,d.legal_entity_id,d.document_type,d.status,d.destination_warehouse_id '
            'FROM inv_document_lines l JOIN inv_documents d ON d.id=l.document_id WHERE l.id=:i',i=origin_id)
        if not row or row['document_type'] not in ('RECEIPT','TRANSFER_DISPATCH') or row['status'] not in ('POSTED','CLOSED'):
            raise HTTPException(409,'HISTORICAL_RECEIPT_OR_DISPATCH_REQUIRED')
        if row['organization_id']!=organization_id or row['warehouse_id']!=warehouse_id or row['item_id']!=item_id:
            raise HTTPException(422,'VALUE_CORRECTION_ORIGIN_SCOPE_MISMATCH')
        if row.get('destination_warehouse_id'):
            await warehouse(self.session,self.request,row['destination_warehouse_id'],'inventory.documents.view')
        return row

    async def apply(self,doc,lines,entity,at):
        authorize(self.request,doc['organization_id'])
        if doc.get('adjustment_kind')!='VALUE' or not (doc.get('reason') or '').strip() or doc.get('source_module'):
            raise HTTPException(422,'DOCUMENTED_VALUE_CORRECTION_REQUIRED')
        for line in lines:
            from .inventory_service import InventoryService
            item=await InventoryService(self.session,self.request)._reference('inv_items',line['item_id'])
            if item['organization_id']!=doc['organization_id'] or item['tracking_policy']!='none':
                raise HTTPException(422,'VALUE_CORRECTION_ITEM_INELIGIBLE')
            if decimal(line['base_quantity'])!=0 or any(line.get(k) for k in ('location_id','destination_location_id','request_line_id','dispatch_line_id')):
                raise HTTPException(422,'VALUE_CORRECTION_CANNOT_MOVE_QUANTITY')
            original=await self.origin(doc['organization_id'],doc['warehouse_id'],line['item_id'],line['origin_line_id'])
            if original['legal_entity_id']!=entity['id'] or original['valuation_currency_id']!=entity['valuation_currency_id']:
                raise HTTPException(422,'VALUE_CORRECTION_OWNER_MISMATCH')
            value=money(line['value_adjustment_amount'])
            if not value:raise HTTPException(422,'NONZERO_VALUE_CORRECTION_REQUIRED')
            state=await self.repo.one('SELECT * FROM inv_valuation_state WHERE legal_entity_id=:l AND item_id=:i AND valuation_currency_id=:c',l=entity['id'],i=line['item_id'],c=entity['valuation_currency_id'])
            if not state:raise HTTPException(409,'VALUATION_UNAVAILABLE')
            before=Valuation(Decimal(state['quantity_total']),Decimal(state['inventory_value']),Decimal(state['avg_cost']));before._validate()
            with localcontext() as ctx:
                ctx.prec=50
                next_value=money(before.inventory_value+value)
                if next_value<0 or (not before.quantity_total and next_value):
                    raise HTTPException(409,'VALUE_CORRECTION_INCONSISTENT_WITH_QUANTITY')
                average=(next_value/before.quantity_total).quantize(COST_SCALE,rounding=ROUND_HALF_UP) if before.quantity_total else Decimal(0)
            Valuation(before.quantity_total,next_value,average)._validate()
            await self.repo.update('inv_document_lines',line['id'],{'valuation_currency_id':entity['valuation_currency_id'],'amount_valuation':str(value)})
            balance=await self.balance(doc,entity,line['item_id'],doc['warehouse_id'],None,'AVAILABLE')
            await self.leg(doc,line,entity,at,balance,doc['warehouse_id'],None,'AVAILABLE',Decimal(0),value,before.avg_cost,'VALUE',new_average=average)
            await self.repo.update('inv_valuation_state',state['id'],{'inventory_value':str(next_value),'avg_cost':str(average),'version':state['version']+1})

    async def references(self,warehouse_id):
        wh=await warehouse(self.session,self.request,warehouse_id,'inventory.documents.create')
        await warehouse(self.session,self.request,warehouse_id,'inventory.documents.view')
        authorize(self.request,wh['organization_id'])
        rows=await self.repo.many("SELECT l.id,l.item_id,d.document_no,d.document_type,d.destination_warehouse_id,l.amount_valuation AS original_value,"
            "v.quantity_total AS current_quantity_total,v.inventory_value AS current_inventory_value,v.avg_cost AS current_avg_cost,c.code AS valuation_currency "
            "FROM inv_document_lines l JOIN inv_documents d ON d.id=l.document_id JOIN inv_items i ON i.id=l.item_id AND i.organization_id=d.organization_id "
            "JOIN inv_warehouse_owners o ON o.warehouse_id=d.warehouse_id AND o.legal_entity_id=d.legal_entity_id "
            "JOIN core_legal_entities e ON e.id=o.legal_entity_id JOIN core_currencies c ON c.id=e.valuation_currency_id "
            "JOIN inv_valuation_state v ON v.legal_entity_id=o.legal_entity_id AND v.item_id=l.item_id AND v.valuation_currency_id=e.valuation_currency_id "
            "WHERE d.warehouse_id=:w AND d.organization_id=:o AND d.status IN ('POSTED','CLOSED') AND d.document_type IN ('RECEIPT','TRANSFER_DISPATCH') ORDER BY d.posted_at DESC,l.id LIMIT 200",w=warehouse_id,o=wh['organization_id'])
        result=[];destinations={}
        for row in rows:
            destination=row.pop('destination_warehouse_id')
            if destination:
                if destination not in destinations:
                    try:
                        await warehouse(self.session,self.request,destination,'inventory.documents.view')
                        destinations[destination]=True
                    except HTTPException as exc:
                        if exc.status_code not in (403,404,409):raise
                        destinations[destination]=False
                if not destinations[destination]:continue
            result.append(row)
        return {'items':result}
