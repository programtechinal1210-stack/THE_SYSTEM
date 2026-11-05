"""Custody is stock possession; only its consumption reduces total inventory."""
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, localcontext, ROUND_HALF_UP
from fastapi import HTTPException
from .transfer_service import TransferPosting
from .inventory_service import InventoryService
from .posting_access import warehouse, costs
from .reservation_service import ReservationService
from ..domain.financial_policy import Valuation, quantity, COST_SCALE


def today():
    return datetime.now(timezone.utc).date()


class CustodyPosting(TransferPosting):
    async def validate_holder(self, kind, identifier, wh):
        user=await self.repo.one('SELECT id,organization_id,is_active,full_name FROM users WHERE id=:i',i=identifier)
        if not user:
            raise HTTPException(422,'CUSTODY_HOLDER_UNAVAILABLE')
        if kind=='ISSUE_CUSTODY' and (not user['is_active'] or not user['organization_id'] or user['organization_id'] not in (wh['organization_id'],wh.get('operating_department_id'))):
            raise HTTPException(422,'ACTIVE_SCOPED_CUSTODY_HOLDER_REQUIRED')
        if kind in ('CONSUMPTION','RETURN_INTERNAL'):
            account=await self.repo.one('SELECT c.location_id FROM inv_custody_accounts c JOIN inv_locations l ON l.id=c.location_id '
                'WHERE c.holder_user_id=:u AND c.organization_id=:o AND l.warehouse_id=:w LIMIT 1',u=identifier,o=wh['organization_id'],w=wh['id'])
            if not account:
                raise HTTPException(422,'CUSTODY_HISTORICAL_HOLDER_SCOPE_MISMATCH')
        return user

    async def apply(self, doc, lines, entity, at):
        wh=await warehouse(self.session,self.request,doc['warehouse_id'],'inventory.documents.post')
        if wh['organization_id']!=doc['organization_id'] or doc.get('source_module'):
            raise HTTPException(422,'CUSTODY_SOURCE_SCOPE_MISMATCH')
        await self.validate_holder(doc['document_type'],doc['beneficiary_user_id'],wh)
        service=InventoryService(self.session,self.request)
        for line in lines:
            item=await service._reference('inv_items',line['item_id'])
            if item['organization_id']!=doc['organization_id'] or item['tracking_policy']!='none':
                raise HTTPException(422,'CUSTODY_ITEM_INELIGIBLE')
            unit=await service._reference('inv_units',item['base_unit_id'])
            q=quantity(line['base_quantity'],unit['precision'])
            for field in ('location_id','destination_location_id'):
                if line[field]:
                    loc=await service._reference('inv_locations',line[field])
                    if loc['warehouse_id']!=wh['id']:
                        raise HTTPException(422,'CUSTODY_LOCATION_SCOPE_MISMATCH')
            issue=doc['document_type']=='ISSUE_CUSTODY'
            source_status='AVAILABLE' if issue else 'CUSTODY'
            if line.get('dispatch_line_id') or (issue and line.get('origin_line_id')):
                raise HTTPException(422,'INVALID_CUSTODY_REFERENCE')
            if issue:
                destination=line['destination_location_id']
                if not destination:
                    raise HTTPException(422,'CUSTODY_LOCATION_REQUIRED')
                account=await self.repo.one('SELECT * FROM inv_custody_accounts WHERE location_id=:i',i=destination)
                if account and (account['holder_user_id']!=doc['beneficiary_user_id'] or account['organization_id']!=doc['organization_id']):
                    raise HTTPException(409,'CUSTODY_LOCATION_HAS_ANOTHER_HOLDER')
                other=await self.repo.many("SELECT quantity_on_hand FROM inv_stock_balances WHERE location_id=:i AND stock_status<>'CUSTODY'",i=destination)
                if any(Decimal(r['quantity_on_hand']) for r in other):
                    raise HTTPException(409,'CUSTODY_LOCATION_MUST_BE_DEDICATED')
                if not account:
                    await self.repo.insert('inv_custody_accounts',{'location_id':destination,'organization_id':doc['organization_id'],
                        'holder_user_id':doc['beneficiary_user_id'],'created_by':self.request.state.user_id.hex,'created_at':at})
            else:
                if line.get('request_line_id'):
                    raise HTTPException(422,'CUSTODY_ALREADY_FULFILLED_REQUEST')
                original=await self.repo.one('SELECT l.*,d.document_type,d.status,d.organization_id,d.legal_entity_id,d.warehouse_id,d.beneficiary_user_id '
                    'FROM inv_document_lines l JOIN inv_effective_documents d ON d.id=l.document_id WHERE l.id=:i',i=line['origin_line_id'])
                if not original or original['document_type']!='ISSUE_CUSTODY' or original['status'] not in ('POSTED','CLOSED'):
                    raise HTTPException(409,'POSTED_CUSTODY_ISSUE_REQUIRED')
                if any(original[k]!=doc[k] for k in ('organization_id','warehouse_id','beneficiary_user_id')) or original['legal_entity_id']!=entity['id'] or original['item_id']!=line['item_id'] or original['destination_location_id']!=line['location_id']:
                    raise HTTPException(422,'CUSTODY_ORIGIN_SCOPE_MISMATCH')
                previous=await self.repo.many("SELECT l.base_quantity FROM inv_document_lines l JOIN inv_effective_documents d ON d.id=l.document_id "
                    "WHERE l.origin_line_id=:i AND d.document_type IN ('CONSUMPTION','RETURN_INTERNAL') "
                    "AND (d.status IN ('POSTED','CLOSED') OR (d.id=:current AND l.line_no<:n))",i=original['id'],current=doc['id'],n=line['line_no'])
                used=sum((Decimal(r['base_quantity']) for r in previous),Decimal(0))
                if used+q>Decimal(original['base_quantity']):
                    raise HTTPException(409,'CUSTODY_ORIGIN_QUANTITY_EXCEEDED')
                account=await self.repo.one('SELECT * FROM inv_custody_accounts WHERE location_id=:i',i=line['location_id'])
                if not account or account['holder_user_id']!=doc['beneficiary_user_id'] or account['organization_id']!=doc['organization_id']:
                    raise HTTPException(409,'CUSTODY_ACCOUNT_UNAVAILABLE')
                if doc['document_type']=='CONSUMPTION' and line['destination_location_id']:
                    raise HTTPException(422,'CONSUMPTION_HAS_NO_DESTINATION')
                if doc['document_type']=='RETURN_INTERNAL' and line['destination_location_id']:
                    reserved_location=await self.repo.one('SELECT location_id FROM inv_custody_accounts WHERE location_id=:i',i=line['destination_location_id'])
                    if reserved_location:
                        raise HTTPException(422,'RETURN_REQUIRES_AVAILABLE_LOCATION')
            source=await self.balance(doc,entity,item['id'],wh['id'],line['location_id'],source_status)
            on_hand=Decimal(source['quantity_on_hand']) if source else Decimal(0)
            if q>on_hand:
                raise HTTPException(409,'INSUFFICIENT_CUSTODY_STOCK' if not issue else 'INSUFFICIENT_STOCK')
            valuation=await self.repo.one('SELECT * FROM inv_valuation_state WHERE legal_entity_id=:l AND item_id=:i AND valuation_currency_id=:c',
                l=entity['id'],i=item['id'],c=entity['valuation_currency_id'])
            if not valuation:
                raise HTTPException(409,'VALUATION_UNAVAILABLE')
            before=Valuation(Decimal(valuation['quantity_total']),Decimal(valuation['inventory_value']),Decimal(valuation['avg_cost']))
            after,value=before.issue(q)
            if issue:
                await ReservationService(self.session,self.request).consume(doc,line,q,on_hand)
            with localcontext() as ctx:
                ctx.prec=50
                cost=(value/q).quantize(COST_SCALE,rounding=ROUND_HALF_UP)
            await self.repo.update('inv_document_lines',line['id'],{'valuation_currency_id':entity['valuation_currency_id'],
                'unit_cost_valuation':str(cost),'amount_valuation':str(value)})
            consumption=doc['document_type']=='CONSUMPTION'
            await self.leg(doc,line,entity,at,source,wh['id'],line['location_id'],source_status,-q,-value,before.avg_cost,'SOURCE',
                new_average=after.avg_cost if consumption else before.avg_cost)
            if consumption:
                await self.repo.update('inv_valuation_state',valuation['id'],{'quantity_total':str(after.quantity_total),
                    'inventory_value':str(after.inventory_value),'avg_cost':str(after.avg_cost),'version':valuation['version']+1})
            else:
                destination=line['destination_location_id']
                status='CUSTODY' if issue else 'AVAILABLE'
                balance=await self.balance(doc,entity,item['id'],wh['id'],destination,status)
                await self.leg(doc,line,entity,at,balance,wh['id'],destination,status,q,value,before.avg_cost,'DESTINATION')

    async def holders(self, warehouse_id):
        wh=await warehouse(self.session,self.request,warehouse_id,'inventory.documents.create')
        await warehouse(self.session,self.request,warehouse_id,'inventory.documents.view')
        rows=await self.repo.many('SELECT DISTINCT u.id,u.full_name,u.is_active,u.organization_id FROM users u '
            'WHERE (u.is_active=1 AND u.organization_id IN (:o,:dept)) OR u.id IN '
            '(SELECT c.holder_user_id FROM inv_custody_accounts c JOIN inv_locations l ON l.id=c.location_id WHERE l.warehouse_id=:w) '
            'ORDER BY u.full_name,u.id',o=wh['organization_id'],dept=wh.get('operating_department_id') or wh['organization_id'],w=warehouse_id)
        return {'items':[{'id':r['id'],'name':r['full_name'],'active_member':bool(r['is_active'] and r['organization_id'] and r['organization_id'] in (wh['organization_id'],wh.get('operating_department_id')))} for r in rows]}

    async def report(self, warehouse_id, references=False, skip=0, limit=200):
        permission='inventory.documents.create' if references else 'inventory.stock.view'
        wh=await warehouse(self.session,self.request,warehouse_id,permission)
        if references:
            await warehouse(self.session,self.request,warehouse_id,'inventory.documents.view')
        issued=await self.repo.many("SELECT l.*,d.document_no,d.beneficiary_user_id,d.custody_due_date,d.organization_id,"
            "u.full_name AS holder_name,i.code AS item_code,i.name_ar AS item_name,loc.name AS location_name,un.name AS unit_name "
            "FROM inv_document_lines l JOIN inv_effective_documents d ON d.id=l.document_id JOIN users u ON u.id=d.beneficiary_user_id "
            "JOIN inv_items i ON i.id=l.item_id JOIN inv_locations loc ON loc.id=l.destination_location_id JOIN inv_units un ON un.id=i.base_unit_id "
            "WHERE d.warehouse_id=:w AND d.document_type='ISSUE_CUSTODY' AND d.status IN ('POSTED','CLOSED') "
            "ORDER BY d.posted_at DESC,l.id LIMIT :limit OFFSET :skip",w=warehouse_id,limit=limit,skip=skip)
        if not issued:
            return {'items':[]}
        bindings={'w':warehouse_id,**{f'i{n}':r['id'] for n,r in enumerate(issued)}}
        source_ids=','.join(':'+f'i{n}' for n in range(len(issued)))
        settled=await self.repo.many("SELECT l.origin_line_id,l.base_quantity,l.amount_valuation,d.document_type "
            "FROM inv_document_lines l JOIN inv_effective_documents d ON d.id=l.document_id WHERE d.warehouse_id=:w AND d.status IN ('POSTED','CLOSED') "
            "AND d.document_type IN ('CONSUMPTION','RETURN_INTERNAL') AND l.origin_line_id IN ("+source_ids+")",**bindings)
        grouped=defaultdict(list)
        for r in settled:
            grouped[r['origin_line_id']].append(r)
        result=[]
        financial=not references and costs(self.request,wh['organization_id'])
        for row in issued:
            rows=grouped[row['id']]
            consumed=sum((Decimal(r['base_quantity']) for r in rows if r['document_type']=='CONSUMPTION'),Decimal(0))
            returned=sum((Decimal(r['base_quantity']) for r in rows if r['document_type']=='RETURN_INTERNAL'),Decimal(0))
            remaining=Decimal(row['base_quantity'])-consumed-returned
            if references and remaining<=0:
                continue
            record={'id':row['id'],'document_no':row['document_no'],'item_id':row['item_id'],'item_code':row['item_code'],
                'item_name':row['item_name'],'unit_name':row['unit_name'],'holder_user_id':row['beneficiary_user_id'],'holder_name':row['holder_name'],
                'location_id':row['destination_location_id'],'location_name':row['location_name'],'issued':row['base_quantity'],
                'consumed':str(consumed),'returned':str(returned),'remaining':str(remaining),'due_date':row['custody_due_date'],
                'status':'INCONSISTENT_CUSTODY' if remaining<0 else ('OPEN' if remaining else 'SETTLED'),'overdue':bool(remaining>0 and row['custody_due_date'] and row['custody_due_date']<today().isoformat())}
            if financial:
                record['consumption_cost']=str(sum((Decimal(r['amount_valuation']) for r in rows if r['document_type']=='CONSUMPTION'),Decimal(0)))
            result.append(record)
        return {'items':result}
