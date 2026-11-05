"""Request lifecycle; quantity fulfillment is written only by the posting engine."""
from decimal import Decimal
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from core.access import require
from core.work_context import organization_allowed
from .inventory_service import InventoryService, now
from ..domain.financial_policy import quantity, decimal
from ..infrastructure.posting_repository import PostingRepository


class RequestService:
    def __init__(self, session, request):
        self.session, self.request = session, request
        self.repo = PostingRepository(session)

    @property
    def actor(self):
        return self.request.state.user_id.hex

    async def scope(self, organization_id, permission):
        require(self.request, permission)
        if not organization_allowed(self.request, permission, organization_id):
            raise HTTPException(404, 'REQUEST_OUTSIDE_SCOPE')
        await InventoryService(self.session, self.request)._check_org(organization_id)

    async def raw(self, identifier, permission):
        require(self.request, permission)
        row = await self.repo.one('SELECT * FROM inv_material_requests WHERE id=:i', i=identifier)
        if not row:
            raise HTTPException(404, 'REQUEST_UNAVAILABLE')
        await self.scope(row['organization_id'], permission)
        return row

    async def detail(self, identifier):
        row = await self.raw(identifier, 'inventory.requests.view')
        row['lines'] = await self.repo.many('SELECT * FROM inv_request_lines WHERE request_id=:i ORDER BY id', i=identifier)
        for line in row['lines']:
            line['remaining_quantity'] = str(Decimal(line['approved_quantity'])-Decimal(line['fulfilled_quantity']))
        # Only scoped documents/reservations may be revealed by their owning APIs.
        return row

    async def listing(self, organization_id, skip, limit, search=None, status=None,
                      date_from=None, date_to=None, department_id=None):
        await self.scope(organization_id, 'inventory.requests.view')
        clauses = ['organization_id=:o']
        params = {'o': organization_id, 'l': limit, 's': skip}
        if search:
            clauses.append('(request_no LIKE :q OR id LIKE :q)')
            params['q'] = '%' + search.strip() + '%'
        if status:
            if status not in {'DRAFT','SUBMITTED','APPROVED','PARTIAL','FULFILLED','CANCELLED','REJECTED','CLOSED'}:
                raise HTTPException(422, 'UNKNOWN_REQUEST_STATUS')
            clauses.append('status=:status')
            params['status'] = status
        if date_from:
            clauses.append('created_at>=:date_from')
            params['date_from'] = date_from
        if date_to:
            clauses.append('created_at<:date_to')
            params['date_to'] = date_to
        if department_id:
            clauses.append('department_id=:department_id')
            params['department_id'] = department_id
        where = ' AND '.join(clauses)
        list_where = (where.replace('organization_id=', 'r.organization_id=')
            .replace('status=', 'r.status=')
            .replace('request_no ', 'r.request_no ')
            .replace('id LIKE', 'r.id LIKE')
            .replace('created_at', 'r.created_at')
            .replace('department_id=', 'r.department_id='))
        if search:
            list_where = list_where.replace(
                '(r.request_no LIKE :q OR r.id LIKE :q)',
                '(r.request_no LIKE :q OR r.id LIKE :q OR d.name LIKE :q)',
            )
        items = await self.repo.many('SELECT r.*,d.name AS department_name,'
            '(SELECT COUNT(*) FROM inv_request_lines l WHERE l.request_id=r.id) AS line_count '
            'FROM inv_material_requests r LEFT JOIN organizations d ON d.id=r.department_id WHERE '+
            list_where+
            ' ORDER BY r.created_at DESC,r.id LIMIT :l OFFSET :s', **params)
        total = await self.repo.one('SELECT COUNT(*) AS total FROM inv_material_requests r '
            'LEFT JOIN organizations d ON d.id=r.department_id WHERE '+list_where, **params)
        counts = await self.repo.many('SELECT status,COUNT(*) AS total FROM inv_material_requests '
            'WHERE organization_id=:o GROUP BY status', o=organization_id)
        return {'items': items, 'total': total['total'] if total else 0,
                'counts': {row['status']: row['total'] for row in counts}}

    async def save(self, data, identifier=None):
        await self.session.execute(text('UPDATE inv_material_requests SET updated_at=updated_at WHERE id=:i'), {'i':identifier or ''})
        await self.scope(data.organization_id.hex, 'inventory.requests.create')
        existing = await self.raw(identifier, 'inventory.requests.create') if identifier else None
        if existing and (existing['status'] != 'DRAFT' or existing['created_by'] != self.actor):
            raise HTTPException(409, 'ONLY_CREATOR_DRAFT_EDIT')
        if existing and existing['organization_id'] != data.organization_id.hex:
            raise HTTPException(422, 'REQUEST_ORGANIZATION_IMMUTABLE')
        if data.department_id:
            # Department must descend from the request organization, never inferred by name.
            cursor, visited = data.department_id.hex, set()
            while cursor != data.organization_id.hex:
                if not cursor or cursor in visited:
                    raise HTTPException(422, 'DEPARTMENT_OUTSIDE_ORGANIZATION')
                visited.add(cursor)
                unit = await self.repo.one('SELECT parent_id,is_active FROM organizations WHERE id=:i', i=cursor)
                if not unit or not unit['is_active']:
                    raise HTTPException(422, 'DEPARTMENT_UNAVAILABLE')
                cursor = unit['parent_id']
        prepared=[]; seen=set()
        service=InventoryService(self.session,self.request)
        for line in data.lines:
            item=await service._reference('inv_items',line.item_id.hex)
            if item['organization_id']!=data.organization_id.hex or item['tracking_policy']!='none' or not item['base_unit_id']:
                raise HTTPException(422,'REQUEST_ITEM_INELIGIBLE')
            if item['id'] in seen:
                raise HTTPException(422,'DUPLICATE_REQUEST_ITEM')
            seen.add(item['id'])
            unit=await service._reference('inv_units',item['base_unit_id'])
            try: q=quantity(line.quantity,unit['precision'])
            except ValueError as exc: raise HTTPException(422,str(exc)) from None
            prepared.append({'id':uuid4().hex,'item_id':item['id'],'quantity':str(q)})
        identifier=identifier or uuid4().hex
        values={'organization_id':data.organization_id.hex,'department_id':data.department_id.hex if data.department_id else None,
                'request_no':data.request_no or (existing['request_no'] if existing else 'REQ-'+identifier[:16]),'updated_at':now()}
        try:
            if existing:
                await self.repo.update('inv_material_requests',identifier,values)
                await self.session.execute(text('DELETE FROM inv_request_lines WHERE request_id=:i'),{'i':identifier})
            else:
                await self.repo.insert('inv_material_requests',{**values,'id':identifier,'created_by':self.actor,'created_at':now()})
            for line in prepared:
                await self.repo.insert('inv_request_lines',{**line,'request_id':identifier})
        except IntegrityError:
            raise HTTPException(409,'REQUEST_REFERENCE_OR_NUMBER_CONFLICT') from None
        self.audit(identifier,existing,{'status':'DRAFT','line_count':len(prepared),**values})
        return {'id':identifier,'status':'DRAFT','request_no':values['request_no']}

    def audit(self, identifier, old, new):
        self.request.state.audit_details={'entity_type':'inventory.request','entity_id':identifier,'old':old,'new':new}

    async def transition(self, identifier, action, data):
        permission='inventory.requests.approve' if action in ('approve','reject','close') else 'inventory.requests.create'
        await self.session.execute(text('UPDATE inv_material_requests SET updated_at=updated_at WHERE id=:i'),{'i':identifier})
        row=await self.raw(identifier,permission)
        status=row['status']; at=now(); values={'updated_at':at}
        if action=='submit':
            if status!='DRAFT' or row['created_by']!=self.actor:
                raise HTTPException(409,'ONLY_CREATOR_SUBMIT_DRAFT')
            values.update(status='SUBMITTED',submitted_by=self.actor,submitted_at=at)
        elif action in ('approve','reject'):
            if status!='SUBMITTED' or row['created_by']==self.actor:
                raise HTTPException(409,'INDEPENDENT_REVIEW_REQUIRED')
            if action=='approve':
                lines=await self.repo.many('SELECT l.*,u.precision FROM inv_request_lines l JOIN inv_items i ON i.id=l.item_id '
                    'JOIN inv_units u ON u.id=i.base_unit_id WHERE l.request_id=:i',i=identifier)
                supplied={k.hex:v for k,v in data.approved_quantities.items()} if data.approved_quantities is not None else None
                if supplied is not None and set(supplied)!={l['id'] for l in lines}:
                    raise HTTPException(422,'APPROVAL_MUST_SPECIFY_ALL_LINES')
                total=Decimal(0)
                for line in lines:
                    try:
                        q=decimal(supplied[line['id']] if supplied is not None else line['quantity'])
                        if q<0 or q>Decimal(line['quantity']): raise ValueError('APPROVAL_OUTSIDE_REQUESTED_QUANTITY')
                        if q: quantity(q,line['precision'])
                    except ValueError as exc: raise HTTPException(422,str(exc)) from None
                    total+=q
                    await self.repo.update('inv_request_lines',line['id'],{'approved_quantity':str(q)})
                if not total: raise HTTPException(422,'APPROVAL_REQUIRES_POSITIVE_QUANTITY')
                values.update(status='APPROVED',approved_by=self.actor,approved_at=at)
            else:
                if not data.reason.strip(): raise HTTPException(422,'DECISION_REASON_REQUIRED')
                values.update(status='REJECTED',closed_by=self.actor,closed_at=at,decision_reason=data.reason.strip())
        elif action in ('cancel','close'):
            permitted=('DRAFT','SUBMITTED','APPROVED','PARTIAL') if action=='cancel' else ('APPROVED','PARTIAL','FULFILLED')
            if status not in permitted or (action=='cancel' and row['created_by']!=self.actor):
                raise HTTPException(409,'REQUEST_TRANSITION_FORBIDDEN')
            if not data.reason.strip(): raise HTTPException(422,'DECISION_REASON_REQUIRED')
            await self.session.execute(text("UPDATE inv_reservations SET status='RELEASED',updated_by=:u,updated_at=:at "
                "WHERE status='ACTIVE' AND request_line_id IN (SELECT id FROM inv_request_lines WHERE request_id=:i)"),
                {'u':self.actor,'at':at,'i':identifier})
            values.update(status='CANCELLED' if action=='cancel' else 'CLOSED',closed_by=self.actor,closed_at=at,decision_reason=data.reason.strip())
        else: raise HTTPException(422,'UNKNOWN_REQUEST_ACTION')
        await self.repo.update('inv_material_requests',identifier,values)
        self.audit(identifier,row,values)
        return {'id':identifier,**values}
