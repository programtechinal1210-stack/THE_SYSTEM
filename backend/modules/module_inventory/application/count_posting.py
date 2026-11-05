"""Approved count differences are posted through the existing ledger writer."""
from decimal import Decimal,localcontext,ROUND_HALF_UP
from uuid import uuid4
from fastapi import HTTPException
from core.access import require
from .stocktake_service import StocktakeService,writer
from .transfer_service import TransferPosting
from .posting_access import warehouse
from .reservation_service import ReservationService
from .inventory_service import now
from ..domain.financial_policy import Valuation,money,COST_SCALE


class CountPosting(TransferPosting):
    async def authorize_document_sources(self,doc,financial=True):
        source=await StocktakeService(self.session,self.request).raw(doc['stocktake_id'])
        await warehouse(self.session,self.request,source['warehouse_id'],'inventory.stock.view')
        if source['warehouse_id']!=doc['warehouse_id'] or source['organization_id']!=doc['organization_id']:raise HTTPException(409,'COUNT_SOURCE_SCOPE_MISMATCH')
        if financial and await self.repo.one("SELECT id FROM inv_document_lines WHERE document_id=:i AND count_cost_basis='APPROVED_EXPLICIT' LIMIT 1",i=doc['id']):
            from .value_correction_service import authorize
            authorize(self.request,doc['organization_id'])
        return source

    async def create(self,identifier,data):
        require(self.request,'inventory.documents.create');await writer(self.session)
        source=await StocktakeService(self.session,self.request).raw(identifier,'inventory.stocktakes.settle')
        await warehouse(self.session,self.request,source['warehouse_id'],'inventory.stocktakes.view')
        await warehouse(self.session,self.request,source['warehouse_id'],'inventory.stock.view')
        await warehouse(self.session,self.request,source['warehouse_id'],'inventory.documents.create')
        if source['status']!='APPROVED' or source['settlement_document_id']:raise HTTPException(409,'APPROVED_UNSETTLED_COUNT_REQUIRED')
        rows=await self.repo.many('SELECT * FROM inv_stocktake_lines WHERE stocktake_id=:i ORDER BY id',i=identifier)
        rows=[r for r in rows if r['approved_difference'] is not None and Decimal(r['approved_difference'])!=0]
        rows.sort(key=lambda r:(Decimal(r['approved_difference'])>0,r['item_id'],r['location_id'] or '',r['stock_status'],r['id']))
        if not rows:raise HTTPException(409,'COUNT_HAS_NO_VARIANCE')
        basis={b.stocktake_line_id.hex:b for b in data.valuation_basis}
        if set(basis)-{r['id'] for r in rows if Decimal(r['approved_difference'])>0}:raise HTTPException(422,'GAIN_BASIS_MUST_REFERENCE_POSITIVE_VARIANCE')
        if basis:
            from .value_correction_service import authorize
            authorize(self.request,source['organization_id'])
        currency=await self.repo.one('SELECT valuation_currency_id FROM core_legal_entities WHERE id=:i',i=source['legal_entity_id'])
        if not currency or not currency['valuation_currency_id']:raise HTTPException(409,'LEGAL_VALUATION_NOT_READY')
        ident=uuid4().hex;at=now()
        await self.repo.insert('inv_documents',{'id':ident,'organization_id':source['organization_id'],'warehouse_id':source['warehouse_id'],
            'document_type':'ADJUSTMENT','adjustment_kind':'COUNT','stocktake_id':identifier,'document_no':'ADJ-CNT-'+ident[:12],
            'document_date':data.document_date.isoformat(),'status':'DRAFT','reason':data.reason.strip(),'created_by':self.request.state.user_id.hex,'created_at':at,'updated_at':at})
        for n,row in enumerate(rows,1):
            delta=Decimal(row['approved_difference']);q=abs(delta);proposal=basis.get(row['id'])
            proposed_amount=None
            if proposal:
                with localcontext() as ctx:
                    ctx.prec=50;proposed_amount=str(money(Decimal(proposal.unit_cost)*q))
            if delta>0 and not proposal:
                valuation=await self.repo.one('SELECT quantity_total FROM inv_valuation_state WHERE legal_entity_id=:l AND item_id=:i AND valuation_currency_id=:c',l=source['legal_entity_id'],i=row['item_id'],c=currency['valuation_currency_id'])
                if not valuation or Decimal(valuation['quantity_total'])<=0:raise HTTPException(409,'EXPLICIT_GAIN_VALUATION_REQUIRED')
            await self.repo.insert('inv_document_lines',{'id':uuid4().hex,'document_id':ident,'line_no':n,'item_id':row['item_id'],'unit_id':row['unit_id'],
                'location_id':row['location_id'],'quantity':str(q),'base_quantity':str(q),'stocktake_line_id':row['id'],
                'count_cost_basis':'APPROVED_EXPLICIT' if proposal else 'CURRENT_WAC',
                'transaction_currency_id':currency['valuation_currency_id'] if proposal else None,'original_unit_price':proposal.unit_cost if proposal else None,
                'original_amount':proposed_amount,
                'adjustment_cost_reason':proposal.reason.strip() if proposal else None})
        self.request.state.audit_details={'entity_type':'inventory.document','entity_id':ident,'old':None,'new':{'document_type':'ADJUSTMENT','adjustment_kind':'COUNT','stocktake_id':identifier,'line_count':len(rows)}}
        return {'id':ident,'status':'DRAFT','stocktake_id':identifier}

    async def apply(self,doc,lines,entity,at):
        source=await self.authorize_document_sources(doc)
        if source['status']!='APPROVED' or source['settlement_document_id'] or source['legal_entity_id']!=entity['id']:raise HTTPException(409,'APPROVED_UNSETTLED_COUNT_REQUIRED')
        originals=await self.repo.many('SELECT * FROM inv_stocktake_lines WHERE stocktake_id=:i ORDER BY id',i=source['id'])
        expected={r['id']:r for r in originals if r['approved_difference'] is not None and Decimal(r['approved_difference'])!=0}
        if len(lines)!=len(expected) or {l['stocktake_line_id'] for l in lines}!=set(expected):raise HTTPException(409,'COUNT_SETTLEMENT_LINES_MISMATCH')
        service=StocktakeService(self.session,self.request)
        ordered=sorted(expected.values(),key=lambda r:(Decimal(r['approved_difference'])>0,r['item_id'],r['location_id'] or '',r['stock_status'],r['id']))
        if [l['stocktake_line_id'] for l in lines]!=[r['id'] for r in ordered]:raise HTTPException(409,'COUNT_SETTLEMENT_ORDER_MISMATCH')
        opening={}
        for line in lines:
            original=expected[line['stocktake_line_id']];delta=Decimal(original['approved_difference']);q=abs(delta)
            if Decimal(line['base_quantity'])!=q or Decimal(line['quantity'])!=q or any(line[k]!=original[k] for k in ('item_id','unit_id','location_id')) or any(line.get(k) for k in ('request_line_id','origin_line_id','dispatch_line_id','destination_location_id')):
                raise HTTPException(409,'COUNT_SETTLEMENT_LINES_MISMATCH')
            item=await service.item(line['item_id'],doc['organization_id'])
            if item['base_unit_id']!=original['unit_id'] or item['unit_precision']!=original['unit_precision']:raise HTTPException(409,'COUNT_UNIT_CHANGED_RESTART')
            balance=await self.balance(doc,entity,line['item_id'],doc['warehouse_id'],line['location_id'],original['stock_status'])
            on_hand=Decimal(balance['quantity_on_hand']) if balance else Decimal(0)
            if on_hand!=Decimal(original['book_quantity']):raise HTTPException(409,'COUNT_BOOK_CHANGED_RECONCILE')
            valuation=await self.repo.one('SELECT * FROM inv_valuation_state WHERE legal_entity_id=:l AND item_id=:i AND valuation_currency_id=:c',l=entity['id'],i=line['item_id'],c=entity['valuation_currency_id'])
            before=Valuation(Decimal(valuation['quantity_total']),Decimal(valuation['inventory_value']),Decimal(valuation['avg_cost'])) if valuation else Valuation.empty()
            before._validate()
            opening.setdefault(line['item_id'],before)
            if delta<0:
                if line['count_cost_basis']!='CURRENT_WAC' or line.get('original_unit_price') is not None:raise HTTPException(409,'COUNT_LOSS_REQUIRES_CURRENT_WAC')
                if original['stock_status']=='AVAILABLE':
                    reserved=ReservationService.amount(await ReservationService(self.session,self.request).outstanding(doc['warehouse_id'],line['item_id'],line['location_id']))
                    if q>on_hand-reserved:raise HTTPException(409,'INSUFFICIENT_UNRESERVED_STOCK')
                after,value=before.issue(q);signed=-value
            else:
                with localcontext() as ctx:
                    ctx.prec=50
                    if line['count_cost_basis']=='APPROVED_EXPLICIT':
                        if line['transaction_currency_id']!=entity['valuation_currency_id'] or not (line.get('adjustment_cost_reason') or '').strip():raise HTTPException(409,'COUNT_CURRENCY_OR_BASIS_CHANGED')
                        value=money(Decimal(line['original_unit_price'])*q)
                    else:
                        basis=opening[line['item_id']]
                        if basis.quantity_total<=0:raise HTTPException(409,'EXPLICIT_GAIN_VALUATION_REQUIRED')
                        value=money(basis.inventory_value*q/basis.quantity_total)
                after=before.receive(q,value);signed=value
            with localcontext() as ctx:
                ctx.prec=50;cost=(abs(signed)/q).quantize(COST_SCALE,rounding=ROUND_HALF_UP)
            financial={'valuation_currency_id':entity['valuation_currency_id'],'unit_cost_valuation':str(cost),'amount_valuation':str(abs(signed))}
            if line['count_cost_basis']=='APPROVED_EXPLICIT':financial.update(original_amount=str(abs(signed)),fx_rate='1',fx_source_ref='approved_stocktake_valuation_basis',fx_effective_at=doc['document_date'])
            await self.repo.update('inv_document_lines',line['id'],financial)
            await self.leg(doc,line,entity,at,balance,doc['warehouse_id'],line['location_id'],original['stock_status'],delta,signed,before.avg_cost,'COUNT',new_average=after.avg_cost)
            values={'quantity_total':str(after.quantity_total),'inventory_value':str(after.inventory_value),'avg_cost':str(after.avg_cost),'version':valuation['version']+1 if valuation else 1}
            if valuation:await self.repo.update('inv_valuation_state',valuation['id'],values)
            else:await self.repo.insert('inv_valuation_state',{**values,'id':uuid4().hex,'legal_entity_id':entity['id'],'item_id':line['item_id'],'valuation_currency_id':entity['valuation_currency_id']})
        await self.repo.update('inv_stocktakes',source['id'],{'status':'SETTLED','settlement_document_id':doc['id'],'settled_by':self.request.state.user_id.hex,'settled_at':at,'updated_at':at})
