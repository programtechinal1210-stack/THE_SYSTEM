"""Scoped, frozen physical counts; settlements use the existing posting engine."""
from decimal import Decimal,localcontext
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import text
from core.access import require
from .inventory_service import now
from .posting_access import warehouse,costs
from ..infrastructure.posting_repository import PostingRepository
from ..domain.financial_policy import decimal,quantity

COUNTABLE={'AVAILABLE','QUARANTINE','DAMAGED'}
ACTIVE=('OPEN','SUBMITTED','APPROVED')


async def writer(session):
    # Same protected SQLite write boundary as document posting, no row changes.
    await session.execute(text('UPDATE inv_stocktakes SET updated_at=updated_at WHERE 0'))


async def check_freeze(session,warehouse_id,item_id,location_id,status,delta,stocktake_id=None):
    if status not in COUNTABLE or Decimal(delta)==0:return
    row=(await session.execute(text("SELECT s.id FROM inv_stocktakes s WHERE s.warehouse_id=:w AND s.status IN ('OPEN','SUBMITTED','APPROVED') "
        "AND (s.all_locations=1 OR COALESCE(s.location_id,'')=:loc) AND (s.stock_status IS NULL OR s.stock_status=:st) "
        "AND (s.all_items=1 OR EXISTS(SELECT 1 FROM inv_stocktake_scope_items i WHERE i.stocktake_id=s.id AND i.item_id=:item)) "
        "AND NOT(s.id=:own AND s.status='APPROVED') LIMIT 1"),{'w':warehouse_id,'loc':location_id or '', 'st':status,'item':item_id,'own':stocktake_id or ''})).first()
    if row:raise HTTPException(409,'STOCKTAKE_FREEZE_ACTIVE')


class StocktakeService:
    def __init__(self,session,request):
        self.session,self.request=session,request;self.repo=PostingRepository(session)

    @property
    def actor(self):return self.request.state.user_id.hex

    async def raw(self,identifier,permission='inventory.stocktakes.view'):
        require(self.request,permission)
        row=await self.repo.one('SELECT * FROM inv_stocktakes WHERE id=:i',i=identifier)
        if not row:raise HTTPException(404,'STOCKTAKE_UNAVAILABLE')
        await warehouse(self.session,self.request,row['warehouse_id'],permission)
        return row

    async def scope_items(self,identifier):
        return {r['item_id'] for r in await self.repo.many('SELECT item_id FROM inv_stocktake_scope_items WHERE stocktake_id=:i',i=identifier)}

    async def in_scope(self,row,item,location,status):
        return status in COUNTABLE and (not row['stock_status'] or row['stock_status']==status) and (row['all_locations'] or row['location_id']==location) and (row['all_items'] or item in await self.scope_items(row['id']))

    async def item(self,item_id,organization_id):
        item=await self.repo.one('SELECT i.*,u.precision AS unit_precision,u.name AS unit_name FROM inv_items i JOIN inv_units u ON u.id=i.base_unit_id WHERE i.id=:i AND i.deleted_at IS NULL AND u.deleted_at IS NULL',i=item_id)
        if not item or item['organization_id']!=organization_id or item['tracking_policy']!='none':raise HTTPException(422,'COUNT_ITEM_INELIGIBLE')
        return item

    async def location(self,location_id,warehouse_id):
        if location_id:
            row=await self.repo.one('SELECT warehouse_id,deleted_at FROM inv_locations WHERE id=:i',i=location_id)
            if not row or row['deleted_at'] or row['warehouse_id']!=warehouse_id:raise HTTPException(422,'COUNT_LOCATION_SCOPE_MISMATCH')
            if await self.repo.one('SELECT location_id FROM inv_custody_accounts WHERE location_id=:i',i=location_id):raise HTTPException(422,'CUSTODY_REQUIRES_HOLDER_COUNT_CONTRACT')

    @staticmethod
    def counted(value,precision):
        number=decimal(value)
        if number<0:raise HTTPException(422,'COUNT_CANNOT_BE_NEGATIVE')
        try:
            if number:quantity(str(number),precision)
        except ValueError as exc:raise HTTPException(422,str(exc)) from None
        return number

    async def create(self,data):
        require(self.request,'inventory.stocktakes.create');await writer(self.session)
        wh=await warehouse(self.session,self.request,data.warehouse_id.hex,'inventory.stocktakes.create')
        await warehouse(self.session,self.request,wh['id'],'inventory.stocktakes.view')
        location=data.location_id.hex if data.location_id else None
        await self.location(location,wh['id'])
        owner=await self.repo.one('SELECT legal_entity_id FROM inv_warehouse_owners WHERE warehouse_id=:w',w=wh['id'])
        if not owner:raise HTTPException(409,'LEGAL_OWNER_NOT_CONFIGURED')
        selected={i.hex for i in data.item_ids}
        for item in selected:await self.item(item,wh['organization_id'])
        active=await self.repo.many("SELECT * FROM inv_stocktakes WHERE warehouse_id=:w AND status IN ('OPEN','SUBMITTED','APPROVED')",w=wh['id'])
        for old in active:
            same_loc=old['all_locations'] or data.all_locations or old['location_id']==location
            same_status=not old['stock_status'] or not data.stock_status or old['stock_status']==data.stock_status
            same_items=old['all_items'] or not selected or bool(selected & await self.scope_items(old['id']))
            if same_loc and same_status and same_items:raise HTTPException(409,'STOCKTAKE_SCOPE_OVERLAP')
        ident=uuid4().hex;at=now()
        row={'id':ident,'organization_id':wh['organization_id'],'warehouse_id':wh['id'],'legal_entity_id':owner['legal_entity_id'],
            'count_no':'CNT-'+ident[:16],'count_type':data.count_type,'status':'OPEN','all_locations':int(data.all_locations),'location_id':location,
            'all_items':int(not selected),'stock_status':data.stock_status,'cutoff_ledger_seq':await self.session.scalar(text('SELECT COALESCE(MAX(ledger_seq),0) FROM inv_stock_ledger')),
            'reason':data.reason.strip(),'created_by':self.actor,'created_at':at,'updated_at':at}
        # Reconcile the scoped quantity truth before snapshotting caches.
        def scoped(r):return r['stock_status'] in COUNTABLE and (not data.stock_status or r['stock_status']==data.stock_status) and (data.all_locations or r['location_id']==location) and (not selected or r['item_id'] in selected)
        key=lambda r:(r['item_id'],r['location_id'],r['stock_status'])
        ledger={}
        history=await self.repo.many('SELECT item_id,location_id,stock_status,quantity_delta FROM inv_stock_ledger WHERE warehouse_id=:w ORDER BY ledger_seq',w=wh['id'])
        with localcontext() as ctx:
            ctx.prec=50
            for leg in history:
                if scoped(leg):ledger[key(leg)]=ledger.get(key(leg),Decimal(0))+Decimal(leg['quantity_delta'])
        balances=await self.repo.many('SELECT * FROM inv_stock_balances WHERE warehouse_id=:w',w=wh['id'])
        for balance in balances:
            if not scoped(balance):continue
            if balance['legal_entity_id']!=owner['legal_entity_id'] or Decimal(balance['quantity_on_hand'])<0 or Decimal(balance['quantity_on_hand'])!=ledger.pop(key(balance),Decimal(0)):
                raise HTTPException(409,'RECONCILE_BEFORE_STOCKTAKE')
        if any(ledger.values()):raise HTTPException(409,'RECONCILE_BEFORE_STOCKTAKE')
        await self.repo.insert('inv_stocktakes',row)
        for item in sorted(selected):await self.repo.insert('inv_stocktake_scope_items',{'stocktake_id':ident,'item_id':item})
        count=0
        for balance in balances:
            if not scoped(balance) or Decimal(balance['quantity_on_hand'])==0:continue
            await self.location(balance['location_id'],wh['id'])
            item=await self.item(balance['item_id'],wh['organization_id'])
            await self.repo.insert('inv_stocktake_lines',{'id':uuid4().hex,'stocktake_id':ident,'item_id':item['id'],'unit_id':item['base_unit_id'],
                'unit_precision':item['unit_precision'],'location_id':balance['location_id'],'stock_status':balance['stock_status'],'book_quantity':balance['quantity_on_hand']});count+=1
        self.audit(ident,None,{**row,'snapshot_lines':count})
        return {'id':ident,'count_no':row['count_no'],'status':'OPEN','snapshot_lines':count,'cutoff_ledger_seq':row['cutoff_ledger_seq']}

    def audit(self,identifier,old,new):
        self.request.state.audit_details={'entity_type':'inventory.stocktake','entity_id':identifier,'old':old,'new':new}

    async def list(self,warehouse_id,skip=0,limit=100):
        await warehouse(self.session,self.request,warehouse_id,'inventory.stocktakes.view')
        return {'items':await self.repo.many('SELECT id,count_no,count_type,status,cutoff_ledger_seq,created_at FROM inv_stocktakes WHERE warehouse_id=:w ORDER BY created_at DESC,id LIMIT :n OFFSET :s',w=warehouse_id,n=limit,s=skip)}

    async def book_visible(self,row):
        try:await warehouse(self.session,self.request,row['warehouse_id'],'inventory.stock.view');return True
        except HTTPException as exc:
            if exc.status_code not in (403,404):raise
            return False

    async def detail(self,identifier,skip=0,limit=200):
        row=await self.raw(identifier);visible=await self.book_visible(row)
        row['scope_item_ids']=sorted(await self.scope_items(identifier));row['book_visible']=visible
        row['total_lines']=await self.session.scalar(text('SELECT count(*) FROM inv_stocktake_lines WHERE stocktake_id=:i'),{'i':identifier})
        row['uncounted_lines']=await self.session.scalar(text('SELECT count(*) FROM inv_stocktake_lines WHERE stocktake_id=:i AND counted_quantity IS NULL'),{'i':identifier})
        lines=await self.repo.many('SELECT l.*,i.code AS item_code,i.name_ar AS item_name,u.name AS unit_name,loc.name AS location_name FROM inv_stocktake_lines l JOIN inv_items i ON i.id=l.item_id JOIN inv_units u ON u.id=l.unit_id LEFT JOIN inv_locations loc ON loc.id=l.location_id WHERE l.stocktake_id=:i ORDER BY i.code,l.location_id,l.stock_status LIMIT :n OFFSET :s',i=identifier,n=limit,s=skip)
        for line in lines:
            final=line['recount_quantity'] if line['recount_quantity'] is not None else line['counted_quantity']
            if visible:line['difference']=str(Decimal(final)-Decimal(line['book_quantity'])) if final is not None else None
            else:
                for field in ['book_quantity','approved_count_quantity','approved_difference']:line.pop(field,None)
            if row['status'] not in ('APPROVED','SETTLED'):
                line.pop('approved_count_quantity',None);line.pop('approved_difference',None)
        row['lines']=lines
        row['settlement_reversed']=bool(row['settlement_document_id'] and await self.repo.one("SELECT id FROM inv_documents WHERE reverses_document_id=:i AND status IN ('POSTED','CLOSED')",i=row['settlement_document_id']))
        return row

    async def record(self,identifier,line_id,data):
        await writer(self.session);row=await self.raw(identifier,'inventory.stocktakes.count')
        if row['status']!='OPEN':raise HTTPException(409,'COUNT_NOT_OPEN')
        line=await self.repo.one('SELECT * FROM inv_stocktake_lines WHERE id=:i AND stocktake_id=:s',i=line_id,s=identifier)
        if not line:raise HTTPException(404,'COUNT_LINE_UNAVAILABLE')
        q=self.counted(data.quantity,line['unit_precision']);at=now()
        if data.recount:
            if line['counted_quantity'] is None or line['counted_by']==self.actor:raise HTTPException(409,'INDEPENDENT_RECOUNT_REQUIRED')
            values={'recount_quantity':str(q),'recount_by':self.actor,'recount_at':at,'recount_reason':data.reason.strip()}
        else:
            if line['recount_quantity'] is not None:raise HTTPException(409,'RECOUNT_ALREADY_RECORDED')
            values={'counted_quantity':str(q),'counted_by':self.actor,'counted_at':at}
        await self.repo.update('inv_stocktake_lines',line_id,values);self.audit(identifier,line,{'line_id':line_id,**values})
        return {'id':line_id,**values}

    async def actions(self,identifier):
        row=await self.raw(identifier)
        async def scoped(permission):
            try:await warehouse(self.session,self.request,row['warehouse_id'],permission);return True
            except HTTPException as exc:
                if exc.status_code not in (403,404):raise
                return False
        create=await scoped('inventory.stocktakes.create');count=await scoped('inventory.stocktakes.count');approve=await scoped('inventory.stocktakes.approve')
        view=await self.book_visible(row);settle=await scoped('inventory.stocktakes.settle') and await scoped('inventory.documents.create')
        counter=await self.repo.one('SELECT id FROM inv_stocktake_lines WHERE stocktake_id=:i AND (counted_by=:u OR recount_by=:u) LIMIT 1',i=identifier,u=self.actor)
        pending=await self.repo.one("SELECT id FROM inv_documents WHERE stocktake_id=:i AND status IN ('SUBMITTED','APPROVED','POSTED','CLOSED') LIMIT 1",i=identifier)
        result={'count':row['status']=='OPEN' and count,'submit':row['status']=='OPEN' and create and row['created_by']==self.actor,
            'approve':row['status']=='SUBMITTED' and approve and view and row['created_by']!=self.actor and row['counted_empty_by']!=self.actor and not counter,
            'reopen':row['status'] in ('SUBMITTED','APPROVED') and approve and not pending,
            'cancel':row['status'] in ACTIVE and create and row['created_by']==self.actor and not pending,
            'settle':row['status']=='APPROVED' and settle and view,'explicit_basis':False}
        try:
            from .value_correction_service import authorize
            authorize(self.request,row['organization_id']);result['explicit_basis']=True
        except HTTPException as exc:
            if exc.status_code!=403:raise
        return result

    async def observed(self,identifier,data):
        await writer(self.session);row=await self.raw(identifier,'inventory.stocktakes.count')
        if row['status']!='OPEN' or data.recount:raise HTTPException(409,'COUNT_NOT_OPEN_OR_INVALID_ROUND')
        loc=data.location_id.hex if data.location_id else None;item_id=data.item_id.hex
        if not await self.in_scope(row,item_id,loc,data.stock_status):raise HTTPException(422,'OBSERVED_STOCK_OUTSIDE_FROZEN_SCOPE')
        await self.location(loc,row['warehouse_id']);item=await self.item(item_id,row['organization_id'])
        if await self.repo.one("SELECT id FROM inv_stocktake_lines WHERE stocktake_id=:s AND item_id=:i AND COALESCE(location_id,'')=:loc AND stock_status=:st",s=identifier,i=item_id,loc=loc or '',st=data.stock_status):raise HTTPException(409,'COUNT_LINE_ALREADY_EXISTS')
        history=await self.repo.many("SELECT quantity_delta FROM inv_stock_ledger WHERE warehouse_id=:w AND item_id=:i AND COALESCE(location_id,'')=:loc AND stock_status=:st AND ledger_seq<=:cutoff",w=row['warehouse_id'],i=item_id,loc=loc or '',st=data.stock_status,cutoff=row['cutoff_ledger_seq'])
        with localcontext() as ctx:
            ctx.prec=50;book=sum((Decimal(r['quantity_delta']) for r in history),Decimal(0))
        q=self.counted(data.quantity,item['unit_precision']);ident=uuid4().hex;at=now()
        values={'id':ident,'stocktake_id':identifier,'item_id':item_id,'unit_id':item['base_unit_id'],'unit_precision':item['unit_precision'],
            'location_id':loc,'stock_status':data.stock_status,'book_quantity':str(book),'counted_quantity':str(q),'counted_by':self.actor,'counted_at':at}
        await self.repo.insert('inv_stocktake_lines',values);self.audit(identifier,None,{'observed_line_id':ident,'counted_quantity':str(q)})
        return {'id':ident,'counted_quantity':str(q)}

    async def decide(self,identifier,action,data):
        permission={'submit':'create','approve':'approve','reopen':'approve','cancel':'create','confirm-empty':'count'}[action]
        await writer(self.session);row=await self.raw(identifier,'inventory.stocktakes.'+permission);at=now()
        lines=await self.repo.many('SELECT * FROM inv_stocktake_lines WHERE stocktake_id=:i',i=identifier)
        values={'updated_at':at,'decision_reason':data.reason}
        if action=='confirm-empty':
            if row['status']!='OPEN' or lines:raise HTTPException(409,'EMPTY_OPEN_COUNT_REQUIRED')
            values.update(counted_empty_by=self.actor,counted_empty_at=at)
        elif action=='submit':
            if row['status']!='OPEN' or row['created_by']!=self.actor:raise HTTPException(409,'COUNT_CREATOR_OPEN_REQUIRED')
            if any(l['counted_quantity'] is None for l in lines) or (not lines and not row['counted_empty_by']):raise HTTPException(409,'COUNT_INCOMPLETE')
            values.update(status='SUBMITTED',submitted_by=self.actor,submitted_at=at)
        elif action=='approve':
            if row['status']!='SUBMITTED':raise HTTPException(409,'SUBMITTED_COUNT_REQUIRED')
            await warehouse(self.session,self.request,row['warehouse_id'],'inventory.stock.view')
            if self.actor==row['created_by'] or self.actor==row['counted_empty_by'] or any(self.actor in (l['counted_by'],l['recount_by']) for l in lines):raise HTTPException(409,'INDEPENDENT_COUNT_APPROVAL_REQUIRED')
            differences=[]
            for line in lines:
                final=line['recount_quantity'] if line['recount_quantity'] is not None else line['counted_quantity']
                if final is None:raise HTTPException(409,'COUNT_INCOMPLETE')
                difference=Decimal(final)-Decimal(line['book_quantity']);differences.append(difference)
                await self.repo.update('inv_stocktake_lines',line['id'],{'approved_count_quantity':final,'approved_difference':str(difference)})
            values.update(status='APPROVED',approved_by=self.actor,approved_at=at)
            if not any(differences):values.update(status='SETTLED',settled_by=self.actor,settled_at=at)
        elif action in ('reopen','cancel'):
            if row['status'] not in (('SUBMITTED','APPROVED') if action=='reopen' else ACTIVE):raise HTTPException(409,'COUNT_STATE_CONFLICT')
            if action=='cancel' and row['created_by']!=self.actor:raise HTTPException(409,'COUNT_CREATOR_REQUIRED')
            if await self.repo.one("SELECT id FROM inv_documents WHERE stocktake_id=:i AND status IN ('SUBMITTED','APPROVED','POSTED','CLOSED') LIMIT 1",i=identifier):raise HTTPException(409,'RESOLVE_COUNT_DOCUMENTS_FIRST')
            values.update(status='OPEN' if action=='reopen' else 'CANCELLED')
            if action=='reopen':values.update(submitted_by=None,submitted_at=None,approved_by=None,approved_at=None)
        await self.repo.update('inv_stocktakes',identifier,values);self.audit(identifier,row,values)
        return {'id':identifier,**values}
