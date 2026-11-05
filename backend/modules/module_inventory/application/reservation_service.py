"""Exact reservations sharing the posting transaction and existing balances."""
import hashlib, json
import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from .inventory_service import InventoryService, now
from .posting_access import warehouse
from .request_service import RequestService
from ..domain.financial_policy import quantity
from ..infrastructure.posting_repository import PostingRepository


class ReservationService:
    def __init__(self, session, request):
        self.session,self.request=session,request
        self.repo=PostingRepository(session)

    async def outstanding(self, warehouse_id, item_id, location_id, request_line_id=None):
        sql="SELECT * FROM inv_reservations WHERE warehouse_id=:w AND item_id=:i AND COALESCE(location_id,'')=:loc "
        sql+="AND status='ACTIVE' AND (expires_at IS NULL OR expires_at>:at)"
        rows=await self.repo.many(sql,w=warehouse_id,i=item_id,loc=location_id or '',at=now())
        return [r for r in rows if request_line_id is None or r['request_line_id']==request_line_id]

    @staticmethod
    def amount(rows):
        return sum((Decimal(r['quantity'])-Decimal(r['fulfilled_qty']) for r in rows),Decimal(0))

    async def line(self, identifier):
        row=await self.repo.one('SELECT l.*,r.organization_id,r.status AS request_status,r.id AS header_id '
            'FROM inv_request_lines l JOIN inv_material_requests r ON r.id=l.request_id WHERE l.id=:i',i=identifier)
        if not row: raise HTTPException(404,'REQUEST_LINE_UNAVAILABLE')
        return row

    async def create(self, data):
        for attempt in range(3):
            try:
                return await self._create(data)
            except OperationalError as exc:
                if not any(s in str(exc).lower() for s in ('database is locked','database table is locked','sqlite_busy','sqlite_locked')):
                    raise
                await self.session.rollback()
                if attempt==2:
                    raise HTTPException(503,'WRITE_CONTENTION_RETRY',headers={'Retry-After':'1'}) from None
                await asyncio.sleep(.05*(attempt+1))

    async def _create(self, data):
        # First mutable statement obtains SQLite's writer before all stock checks.
        await self.session.execute(text('UPDATE inv_material_requests SET updated_at=updated_at '
            'WHERE id=(SELECT request_id FROM inv_request_lines WHERE id=:i)'),{'i':data.request_line_id.hex})
        wh=await warehouse(self.session,self.request,data.warehouse_id.hex,'inventory.reservations.manage')
        line=await self.line(data.request_line_id.hex)
        await RequestService(self.session,self.request).scope(line['organization_id'],'inventory.reservations.manage')
        if wh['organization_id']!=line['organization_id']:
            raise HTTPException(422,'RESERVATION_SCOPE_MISMATCH')
        service=InventoryService(self.session,self.request)
        item=await service._reference('inv_items',line['item_id'])
        if item['organization_id']!=line['organization_id'] or item['tracking_policy']!='none' or not item['base_unit_id']:
            raise HTTPException(422,'RESERVATION_ITEM_INELIGIBLE')
        unit=await service._reference('inv_units',item['base_unit_id'])
        try: q=quantity(data.quantity,unit['precision'])
        except ValueError as exc: raise HTTPException(422,str(exc)) from None
        loc=data.location_id.hex if data.location_id else None
        if loc:
            location=await service._reference('inv_locations',loc)
            if location['warehouse_id']!=wh['id']: raise HTTPException(422,'LOCATION_WAREHOUSE_MISMATCH')
        expiry=data.expires_at.isoformat() if data.expires_at else None
        normalized={'request_line_id':line['id'],'warehouse_id':wh['id'],'location_id':loc,'quantity':str(q),'expires_at':expiry}
        fingerprint=hashlib.sha256(json.dumps(normalized,sort_keys=True).encode()).hexdigest()
        existing=await self.repo.one('SELECT * FROM inv_reservations WHERE organization_id=:o AND reservation_key=:k',o=line['organization_id'],k=data.reservation_key)
        if existing:
            if existing['payload_hash']!=fingerprint: raise HTTPException(409,'RESERVATION_KEY_REUSED')
            return {**existing,'replayed':True}
        if line['request_status'] not in ('APPROVED','PARTIAL'):
            raise HTTPException(409,'APPROVED_REQUEST_REQUIRED')
        if data.expires_at and data.expires_at<=datetime.now(timezone.utc):
            raise HTTPException(422,'RESERVATION_EXPIRY_IN_PAST')
        owner=await self.repo.one('SELECT o.*,e.status FROM inv_warehouse_owners o JOIN core_legal_entities e ON e.id=o.legal_entity_id WHERE warehouse_id=:w',w=wh['id'])
        if not owner or owner['status']!='approved': raise HTTPException(409,'LEGAL_OWNER_NOT_CONFIGURED')
        all_line=await self.repo.many("SELECT * FROM inv_reservations WHERE request_line_id=:i AND status='ACTIVE' AND (expires_at IS NULL OR expires_at>:at)",i=line['id'],at=now())
        if q+self.amount(all_line)>Decimal(line['approved_quantity'])-Decimal(line['fulfilled_quantity']):
            raise HTTPException(409,'REQUEST_RESERVATION_EXCEEDED')
        stock=await self.repo.one("SELECT quantity_on_hand FROM inv_stock_balances WHERE warehouse_id=:w AND item_id=:i AND legal_entity_id=:owner AND COALESCE(location_id,'')=:loc AND stock_status='AVAILABLE'",w=wh['id'],i=item['id'],owner=owner['legal_entity_id'],loc=loc or '')
        available=Decimal(stock['quantity_on_hand']) if stock else Decimal(0)
        if q>available-self.amount(await self.outstanding(wh['id'],item['id'],loc)):
            raise HTTPException(409,'RESERVATION_OVERCOMMITTED')
        at=now(); actor=self.request.state.user_id.hex
        record={'id':uuid4().hex,'organization_id':line['organization_id'],'legal_entity_id':owner['legal_entity_id'],
                'item_id':item['id'],**normalized,'reservation_key':data.reservation_key,'payload_hash':fingerprint,
                'created_by':actor,'created_at':at,'updated_by':actor,'updated_at':at}
        await self.repo.insert('inv_reservations',record)
        self.request.state.audit_details={'entity_type':'inventory.reservation','entity_id':record['id'],'new':record}
        return {**record,'status':'ACTIVE','fulfilled_qty':'0','replayed':False}

    async def listing(self, warehouse_id):
        await warehouse(self.session,self.request,warehouse_id,'inventory.reservations.view')
        return {'items':await self.repo.many('SELECT * FROM inv_reservations WHERE warehouse_id=:w ORDER BY created_at DESC,id LIMIT 200',w=warehouse_id)}

    async def release(self, identifier, expire=False):
        await self.session.execute(text('UPDATE inv_reservations SET updated_at=updated_at WHERE id=:i'),{'i':identifier})
        row=await self.repo.one('SELECT * FROM inv_reservations WHERE id=:i',i=identifier)
        if not row: raise HTTPException(404,'RESERVATION_UNAVAILABLE')
        await warehouse(self.session,self.request,row['warehouse_id'],'inventory.reservations.manage')
        if expire and (not row['expires_at'] or row['expires_at']>now()):
            raise HTTPException(409,'RESERVATION_NOT_EXPIRED')
        if row['status']!='ACTIVE': return {**row,'replayed':True}
        values={'status':'EXPIRED' if expire else 'RELEASED','updated_at':now(),'updated_by':self.request.state.user_id.hex}
        await self.repo.update('inv_reservations',identifier,values)
        self.request.state.audit_details={'entity_type':'inventory.reservation','entity_id':identifier,'old':row,'new':values}
        return {**row,**values}

    async def consume(self, doc, line, q, on_hand):
        rows=await self.outstanding(doc['warehouse_id'],line['item_id'],line['location_id'])
        source=line.get('request_line_id')
        own=[r for r in rows if source and r['request_line_id']==source]
        protected=self.amount(rows)-self.amount(own)
        if q>on_hand-protected: raise HTTPException(409,'INSUFFICIENT_UNRESERVED_STOCK')
        if not source: return
        request_line=await self.line(source)
        if request_line['organization_id']!=doc['organization_id'] or request_line['item_id']!=line['item_id']:
            raise HTTPException(422,'REQUEST_ISSUE_SCOPE_MISMATCH')
        if request_line['request_status'] not in ('APPROVED','PARTIAL'):
            raise HTTPException(409,'APPROVED_REQUEST_REQUIRED')
        fulfilled=Decimal(request_line['fulfilled_quantity'])+q
        if fulfilled>Decimal(request_line['approved_quantity']):
            raise HTTPException(409,'ISSUE_EXCEEDS_APPROVED_REQUEST')
        remaining=q
        for row in sorted(own,key=lambda r:(r['created_at'],r['id'])):
            used=min(remaining,Decimal(row['quantity'])-Decimal(row['fulfilled_qty']))
            if not used: continue
            amount=Decimal(row['fulfilled_qty'])+used; remaining-=used
            await self.repo.update('inv_reservations',row['id'],{'fulfilled_qty':str(amount),
                'status':'FULFILLED' if amount==Decimal(row['quantity']) else 'ACTIVE',
                'updated_at':now(),'updated_by':self.request.state.user_id.hex})
        await self.repo.update('inv_request_lines',source,{'fulfilled_quantity':str(fulfilled)})
        all_lines=await self.repo.many('SELECT approved_quantity,fulfilled_quantity FROM inv_request_lines WHERE request_id=:i',i=request_line['header_id'])
        done=all(Decimal(r['fulfilled_quantity'])==Decimal(r['approved_quantity']) for r in all_lines)
        await self.repo.update('inv_material_requests',request_line['header_id'],{'status':'FULFILLED' if done else 'PARTIAL','updated_at':now()})
