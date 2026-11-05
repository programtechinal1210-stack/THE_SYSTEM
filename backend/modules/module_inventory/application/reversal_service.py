"""Exact inverse legs, using the existing document, balance and writer contracts."""
from decimal import Decimal, localcontext, ROUND_HALF_UP
from uuid import uuid4
from fastapi import HTTPException
from core.access import require
from .transfer_service import TransferPosting
from .posting_access import warehouse
from .inventory_service import now
from .reservation_service import ReservationService
from ..domain.financial_policy import Valuation, decimal, money, COST_SCALE


class ReversalPosting(TransferPosting):
    async def access(self, original):
        require(self.request,'inventory.documents.reverse')
        targets={original['warehouse_id'],original.get('destination_warehouse_id')}-{None}
        for target in targets:
            await warehouse(self.session,self.request,target,'inventory.documents.reverse')
            await warehouse(self.session,self.request,target,'inventory.documents.view')
        if original['document_type']=='ADJUSTMENT':
            if original['adjustment_kind']=='COUNT':
                from .count_posting import CountPosting
                await CountPosting(self.session,self.request).authorize_document_sources(original)
            else:
                from .value_correction_service import ValueCorrectionPosting
                await ValueCorrectionPosting(self.session,self.request).authorize_document_sources(original)

    async def original(self, identifier):
        original=await self.repo.one('SELECT * FROM inv_documents WHERE id=:i',i=identifier)
        if not original:raise HTTPException(404,'REVERSAL_ORIGINAL_UNAVAILABLE')
        await self.access(original)
        if original['status'] not in ('POSTED','CLOSED') or original['document_type']=='REVERSAL':
            raise HTTPException(409,'POSTED_NON_REVERSAL_REQUIRED')
        if original.get('source_module'):
            raise HTTPException(409,'EXTERNAL_SOURCE_REQUIRES_OWNER_COMPENSATION')
        if await self.repo.one('SELECT id FROM eq_part_lifecycles WHERE installation_inventory_document_id=:i OR removal_inventory_document_id=:i LIMIT 1',i=identifier):
            raise HTTPException(409,'EXTERNAL_PART_REQUIRES_OWNER_COMPENSATION')
        return original

    async def eligible(self, original):
        if await self.repo.one("SELECT id FROM inv_documents WHERE reverses_document_id=:i AND status IN ('POSTED','CLOSED')",i=original['id']):
            raise HTTPException(409,'DOCUMENT_ALREADY_REVERSED')
        child=await self.repo.one("SELECT d.id FROM inv_document_lines l JOIN inv_effective_documents d ON d.id=l.document_id "
            "WHERE d.status IN ('POSTED','CLOSED') AND NOT(d.document_type='ADJUSTMENT' AND d.adjustment_kind='VALUE') AND (l.origin_line_id IN "
            "(SELECT id FROM inv_document_lines WHERE document_id=:i) OR l.dispatch_line_id IN "
            "(SELECT id FROM inv_document_lines WHERE document_id=:i)) LIMIT 1",i=original['id'])
        if child:raise HTTPException(409,'REVERSE_ACTIVE_SETTLEMENTS_FIRST')

    async def create(self, identifier, data):
        require(self.request,'inventory.documents.create')
        original=await self.original(identifier)
        await warehouse(self.session,self.request,original['warehouse_id'],'inventory.documents.create')
        if original.get('destination_warehouse_id'):
            await warehouse(self.session,self.request,original['destination_warehouse_id'],'inventory.documents.create')
        await self.eligible(original)
        if data.document_date.isoformat()<original['document_date']:
            raise HTTPException(422,'REVERSAL_DATE_PRECEDES_ORIGINAL')
        ident=uuid4().hex;at=now()
        values={key:original[key] for key in ('organization_id','warehouse_id','destination_warehouse_id','beneficiary_user_id')}
        values.update(id=ident,document_no='REV-'+ident[:16],document_type='REVERSAL',status='DRAFT',
            document_date=data.document_date.isoformat(),created_by=self.request.state.user_id.hex,created_at=at,updated_at=at,
            reason=data.reason.strip(),reverses_document_id=identifier)
        await self.repo.insert('inv_documents',values)
        for line in await self.repo.many('SELECT * FROM inv_document_lines WHERE document_id=:i ORDER BY line_no',i=identifier):
            line.update(id=uuid4().hex,document_id=ident)
            await self.repo.insert('inv_document_lines',line)
        self.request.state.audit_details={'entity_type':'inventory.document','entity_id':ident,'old':None,
            'new':{'document_type':'REVERSAL','reverses_document_id':identifier,'reason':data.reason.strip()}}
        return {'id':ident,'status':'DRAFT','reverses_document_id':identifier}

    async def apply(self, doc, lines, entity, at):
        original=await self.original(doc['reverses_document_id'])
        await self.eligible(original)
        if doc['document_date']<original['document_date']:
            raise HTTPException(409,'REVERSAL_DATE_PRECEDES_ORIGINAL')
        if original['organization_id']!=doc['organization_id'] or original['warehouse_id']!=doc['warehouse_id'] or original['legal_entity_id']!=entity['id']:
            raise HTTPException(409,'REVERSAL_OWNER_SCOPE_MISMATCH')
        original_lines=await self.repo.many('SELECT * FROM inv_document_lines WHERE document_id=:i ORDER BY line_no',i=original['id'])
        if len(lines)!=len(original_lines):raise HTTPException(409,'REVERSAL_LINES_MISMATCH')
        for line,source in zip(lines,original_lines):
            if any(line[k]!=source[k] for k in source if k not in ('id','document_id')):
                raise HTTPException(409,'REVERSAL_LINES_MISMATCH')
            legs=await self.repo.many('SELECT * FROM inv_stock_ledger WHERE document_line_id=:i ORDER BY ledger_seq DESC',i=source['id'])
            if not legs or any(l['legal_entity_id']!=entity['id'] or l['valuation_currency_id']!=entity['valuation_currency_id'] for l in legs):
                raise HTTPException(409,'REVERSAL_LEDGER_SCOPE_MISMATCH')
            valuation=await self.repo.one('SELECT * FROM inv_valuation_state WHERE legal_entity_id=:l AND item_id=:i AND valuation_currency_id=:c',l=entity['id'],i=source['item_id'],c=entity['valuation_currency_id'])
            if not valuation:raise HTTPException(409,'VALUATION_UNAVAILABLE')
            before=Valuation(Decimal(valuation['quantity_total']),Decimal(valuation['inventory_value']),Decimal(valuation['avg_cost']));before._validate()
            with localcontext() as ctx:
                ctx.prec=50
                q=decimal(before.quantity_total-sum((Decimal(l['quantity_delta']) for l in legs),Decimal(0)))
                v=money(before.inventory_value-sum((Decimal(l['value_delta_valuation']) for l in legs),Decimal(0)))
                if q<0 or v<0 or (q==0 and v!=0):raise HTTPException(409,'REVERSAL_REQUIRES_VALUATION_CORRECTION')
                avg=(v/q).quantize(COST_SCALE,rounding=ROUND_HALF_UP) if q else Decimal(0)
            after=Valuation(q,v,avg);after._validate()
            for n,leg in enumerate(legs):
                await warehouse(self.session,self.request,leg['warehouse_id'],'inventory.documents.reverse')
                balance=await self.balance(doc,entity,source['item_id'],leg['warehouse_id'],leg['location_id'],leg['stock_status'])
                on_hand=Decimal(balance['quantity_on_hand']) if balance else Decimal(0)
                dq=-Decimal(leg['quantity_delta']);dv=-Decimal(leg['value_delta_valuation'])
                if dq<0 and leg['stock_status']=='AVAILABLE':
                    reserved=ReservationService.amount(await ReservationService(self.session,self.request).outstanding(leg['warehouse_id'],source['item_id'],leg['location_id']))
                    if -dq>on_hand-reserved:raise HTTPException(409,'INSUFFICIENT_UNRESERVED_STOCK')
                await self.leg(doc,line,entity,at,balance,leg['warehouse_id'],leg['location_id'],leg['stock_status'],dq,dv,before.avg_cost,'REVERSE-'+str(n),new_average=after.avg_cost)
            await self.repo.update('inv_valuation_state',valuation['id'],{'quantity_total':str(q),'inventory_value':str(v),'avg_cost':str(avg),'version':valuation['version']+1})
            if original['document_type'] in ('ISSUE_DIRECT','ISSUE_CUSTODY') and source.get('request_line_id'):
                await self.restore_request(source)

    async def restore_request(self, source):
        line=await self.repo.one('SELECT l.*,r.status AS header_status FROM inv_request_lines l JOIN inv_material_requests r ON r.id=l.request_id WHERE l.id=:i',i=source['request_line_id'])
        if not line:raise HTTPException(409,'REVERSAL_REQUEST_UNAVAILABLE')
        fulfilled=Decimal(line['fulfilled_quantity'])-Decimal(source['base_quantity'])
        if fulfilled<0:raise HTTPException(409,'REVERSAL_REQUEST_FULFILLMENT_INCONSISTENT')
        await self.repo.update('inv_request_lines',line['id'],{'fulfilled_quantity':str(fulfilled)})
        if line['header_status'] in ('FULFILLED','PARTIAL','APPROVED'):
            all_lines=await self.repo.many('SELECT approved_quantity,fulfilled_quantity FROM inv_request_lines WHERE request_id=:i',i=line['request_id'])
            status='FULFILLED' if all(Decimal(l['fulfilled_quantity'])==Decimal(l['approved_quantity']) for l in all_lines) else ('PARTIAL' if any(Decimal(l['fulfilled_quantity'])>0 for l in all_lines) else 'APPROVED')
            await self.repo.update('inv_material_requests',line['request_id'],{'status':status,'updated_at':now()})
