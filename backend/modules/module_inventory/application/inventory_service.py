"""Inventory foundation service: org-scoped CRUD sharing Core access and recycle."""
from datetime import datetime, timezone
from uuid import UUID, uuid4
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from core.access import require
from core import soft_delete
from ..domain.catalog import KINDS
from ..infrastructure.inventory_repository import InventoryRepository
from .catalog_validation import CatalogValidation


def now():
    return datetime.now(timezone.utc).isoformat()


def permission(kind, action):
    return 'inventory.' + kind + '.' + ('view' if action == 'view' else 'manage')


def in_scope(row, actor, admin, scopes):
    org = row.get('organization_id') if isinstance(row, dict) else None
    if admin or 'institution' in scopes:
        return True
    ao = getattr(getattr(actor, 'organization_id', None), 'hex', None) or getattr(actor, 'organization_id', None)
    return bool('organization' in scopes and org and ao and str(org) == str(ao))


class InventoryService(CatalogValidation):
    def __init__(self, session, request=None):
        self.session, self.request = session, request
        self.repo = InventoryRepository(session)

    def _actor_org(self):
        a = self.request.state.user
        return getattr(getattr(a, 'organization_id', None), 'hex', None) or getattr(a, 'organization_id', None)

    async def _check_org(self, oid):
        # Validate existence as well as syntax; scope is checked separately.
        from uuid import UUID as _UUID
        try:
            _UUID(str(oid)).hex
        except (ValueError, AttributeError, TypeError):
            raise HTTPException(422, 'Unknown organization')
        rows = (await self.session.execute(
            text("SELECT is_active FROM organizations WHERE replace(id,'-','')=:id"),
            {'id': str(oid).replace('-', '')})).mappings().all()
        if not rows:
            raise HTTPException(422, 'Unknown organization')
        for r in rows:
            if not r['is_active']:
                raise HTTPException(422, 'Inactive organization')

    def _scope(self, code):
        return self.request.state.permission_scopes.get(code, {'self'})

    def _allows_org(self, row, code):
        from core.work_context import organization_allowed
        return organization_allowed(self.request, code, row['organization_id'])

    def _audit(self, kind, identifier, old, new):
        if self.request is not None:
            self.request.state.audit_details = {'entity_type': 'inventory.' + kind,
                'entity_id': identifier, 'old': old, 'new': new}

    async def list(self, kind, organization_id=None, search=None, skip=0, limit=50,
                   category_id=None, is_active=None, item_type=None):
        code = permission(kind, 'view')
        require(self.request, code)
        if KINDS[kind][5]:
            if not organization_id:
                from core.work_context import context
                organization_id = (await context(self.session, self.request))['selected_id']
            if not organization_id or not self._allows_org({'organization_id': organization_id}, code):
                raise HTTPException(404, 'Inventory scope unavailable')
        return {'items': await self.repo.list(
            kind, organization_id, search, skip, limit, category_id, is_active, item_type,
        )}

    async def detail(self, kind, entity_id):
        code = permission(kind, 'view')
        require(self.request, code)
        row = await self.repo.get(kind, entity_id)
        if not row or row.get('deleted_at'):
            raise HTTPException(404, 'Inventory item unavailable')
        if KINDS[kind][5] and not self._allows_org(row, code):
            raise HTTPException(404, 'Inventory item unavailable within scope')
        return row
    async def create(self, kind, payload):
        code = permission(kind, 'manage')
        require(self.request, code)
        values = payload.model_dump(mode='json')
        _, _, code_field, _, _, org_scoped = KINDS[kind]
        if org_scoped:
            if not values.get('organization_id'):
                values['organization_id'] = self._actor_org()
            values['organization_id'] = UUID(str(values['organization_id'])).hex
            await self._check_org(values['organization_id'])
            if not self._allows_org(values, code):
                raise HTTPException(403, 'Outside assigned organization scope')
        for k, v in list(values.items()):
            if k.endswith('_id') and v:
                try:
                    values[k] = UUID(str(v)).hex
                except ValueError:
                    raise HTTPException(422, f'Invalid {k}')
        values['id'] = uuid4().hex
        values['created_at'] = now()
        values['updated_at'] = now()
        await self._validate(kind, values, values['id'])
        try:
            await self.repo.save(kind, values['id'], values, create=True)
        except IntegrityError:
            raise HTTPException(409, f'{code_field} exists in scope') from None
        saved = await self.repo.get(kind, values['id'])
        self._audit(kind, values['id'], None, saved)
        return saved

    async def update(self, kind, entity_id, payload):
        code = permission(kind, 'manage')
        require(self.request, code)
        row = await self.repo.get(kind, entity_id)
        if not row or row.get('deleted_at'):
            raise HTTPException(404, 'Inventory item unavailable')
        if KINDS[kind][5] and not self._allows_org(row, code):
            raise HTTPException(404, 'Inventory item unavailable within scope')
        values = {k: v for k, v in payload.model_dump(mode='json', exclude_unset=True).items()
                  if k not in ('organization_id',)}
        for k, v in list(values.items()):
            if k.endswith('_id') and v:
                try:
                    values[k] = UUID(str(v)).hex
                except ValueError:
                    raise HTTPException(422, f'Invalid {k}')
        values['updated_at'] = now()
        await self._validate(kind, {**row, **values}, entity_id)
        try:
            await self.repo.save(kind, entity_id, values)
        except IntegrityError:
            raise HTTPException(409, 'Code exists in scope') from None
        saved = await self.repo.get(kind, entity_id)
        self._audit(kind, entity_id, row, saved)
        return saved

    async def delete(self, kind, entity_id, reason=''):
        code = permission(kind, 'manage')
        require(self.request, code)
        row = await self.repo.get(kind, entity_id)
        if not row or row.get('deleted_at'):
            raise HTTPException(404, 'Inventory item unavailable')
        if KINDS[kind][5] and not self._allows_org(row, code):
            raise HTTPException(404, 'Inventory item unavailable within scope')
        if kind in ('items', 'warehouses'):
            await self._protect_stock('item_id' if kind == 'items' else 'warehouse_id', entity_id)
        if kind == 'categories':
            c = await self.session.scalar(text(
                'SELECT 1 FROM inv_categories WHERE parent_id=:i AND deleted_at IS NULL LIMIT 1'), {'i': entity_id})
            if c:
                raise HTTPException(409, 'Delete sub-categories first')
            u = await self.session.scalar(text(
                'SELECT 1 FROM inv_items WHERE category_id=:i AND deleted_at IS NULL LIMIT 1'), {'i': entity_id})
            if u:
                raise HTTPException(409, 'Category is used by items')
        if kind == 'warehouses':
            c = await self.session.scalar(text(
                'SELECT 1 FROM inv_warehouses WHERE parent_id=:i AND deleted_at IS NULL LIMIT 1'), {'i': entity_id})
            if c:
                raise HTTPException(409, 'Delete child warehouses first')
            if await self.session.scalar(text('SELECT 1 FROM inv_locations WHERE warehouse_id=:i AND deleted_at IS NULL LIMIT 1'), {'i': entity_id}):
                raise HTTPException(409, 'Delete warehouse locations first')
        if kind == 'units':
            await self._unit_unused(entity_id)
        await self.repo.save(kind, entity_id, {'deleted_at': now(),
                                              'deleted_by': self.request.state.user_id.hex,
                                              'updated_at': now()})
        await soft_delete.soft_delete(self.session, 'inventory.' + kind, entity_id,
                                      self.request.state.user_id, reason or None,
                                      {'code': row.get('code')})
        self._audit(kind, entity_id, row, await self.repo.get(kind, entity_id))

    async def recover(self, kind, entity_id, actor_id, purge=False):
        row = await self.repo.get(kind, entity_id)
        if not row or not row.get('deleted_at'):
            raise HTTPException(409, 'Item is not deleted')
        if purge:
            try:
                # Savepoint leaves the caller transaction intact on a protected FK.
                async with self.session.begin_nested():
                    await self.session.execute(text(f'DELETE FROM {KINDS[kind][0]} WHERE id=:id'), {'id': entity_id})
            except IntegrityError:
                raise HTTPException(409, 'Inventory history still references this record') from None
            return
        await self._validate(kind, row, entity_id)
        await self.repo.save(kind, entity_id, {'deleted_at': None, 'deleted_by': None, 'updated_at': now()})
        await soft_delete.restore(self.session, 'inventory.' + kind, entity_id, actor_id)

    async def location(self, warehouse_id, location_id):
        row = (await self.session.execute(text(
            'SELECT * FROM inv_locations WHERE id=:i AND warehouse_id=:w AND deleted_at IS NULL'),
            {'i': location_id, 'w': warehouse_id})).mappings().first()
        if not row:
            raise HTTPException(404, 'Location unavailable')
        return dict(row)

    async def update_location(self, warehouse_id, location_id, payload):
        wh = await self._owned('warehouses', warehouse_id, 'manage')
        if wh['status'] != 'active':
            raise HTTPException(409, 'Warehouse is not active')
        old = await self.location(warehouse_id, location_id)
        values = payload.model_dump(mode='json')
        if values.get('parent_id'):
            values['parent_id'] = UUID(values['parent_id']).hex
        await self._parent('inv_locations', values.get('parent_id'), location_id, 'warehouse_id', warehouse_id)
        try:
            await self.session.execute(text(
                'UPDATE inv_locations SET code=:code,name=:name,parent_id=:parent_id,location_type=:location_type WHERE id=:id'),
                {**values, 'id': location_id})
        except IntegrityError:
            raise HTTPException(409, 'Location code exists in warehouse') from None
        saved = await self.location(warehouse_id, location_id)
        self._audit('locations', location_id, old, saved)
        return saved

    async def delete_location(self, warehouse_id, location_id):
        await self._owned('warehouses', warehouse_id, 'manage')
        row = await self.location(warehouse_id, location_id)
        await self._protect_stock('location_id', location_id)
        if await self.session.scalar(text(
                'SELECT 1 FROM inv_locations WHERE parent_id=:i AND deleted_at IS NULL LIMIT 1'), {'i': location_id}):
            raise HTTPException(409, 'Delete child locations first')
        await self.session.execute(text('UPDATE inv_locations SET deleted_at=:at WHERE id=:id'),
                                   {'at': now(), 'id': location_id})
        await soft_delete.soft_delete(self.session, 'inventory.locations', location_id,
                                      self.request.state.user_id, metadata={'code': row['code']})
        self._audit('locations', location_id, row, {**row, 'deleted_at': now()})

    async def recover_location(self, location_id, actor_id, purge=False):
        row = (await self.session.execute(text('SELECT * FROM inv_locations WHERE id=:i'),
                                          {'i': location_id})).mappings().first()
        if not row or not row['deleted_at']:
            raise HTTPException(409, 'Location is not deleted')
        if purge:
            try:
                async with self.session.begin_nested():
                    await self.session.execute(text('DELETE FROM inv_locations WHERE id=:i'), {'i': location_id})
            except IntegrityError:
                raise HTTPException(409, 'Location is still referenced') from None
            return
        warehouse = await self._reference('inv_warehouses', row['warehouse_id'])
        if warehouse['status'] != 'active':
            raise HTTPException(409, 'Restore the active warehouse first')
        await self._parent('inv_locations', row['parent_id'], location_id, 'warehouse_id', row['warehouse_id'])
        await self.session.execute(text('UPDATE inv_locations SET deleted_at=NULL WHERE id=:i'), {'i': location_id})
        await soft_delete.restore(self.session, 'inventory.locations', location_id, actor_id)

    async def list_locations(self, warehouse_id):
        await self._owned('warehouses', warehouse_id)
        rows = (await self.session.execute(text(
            'SELECT * FROM inv_locations WHERE warehouse_id=:w AND deleted_at IS NULL ORDER BY code'),
            {'w': warehouse_id})).mappings()
        return {'items': [dict(r) for r in rows]}

    async def create_location(self, warehouse_id, payload):
        warehouse = await self._owned('warehouses', warehouse_id, 'manage')
        if warehouse['status'] != 'active':
            raise HTTPException(409, 'Warehouse is not active')
        values = payload.model_dump(mode='json')
        if values.get('parent_id'):
            values['parent_id'] = UUID(str(values['parent_id'])).hex
        values.update({'id': uuid4().hex, 'warehouse_id': warehouse_id, 'created_at': now()})
        await self._parent('inv_locations', values.get('parent_id'), values['id'], 'warehouse_id', warehouse_id)
        try:
            await self.session.execute(text(
                'INSERT INTO inv_locations (id,warehouse_id,parent_id,code,name,location_type,is_active,created_at)'
                ' VALUES (:id,:warehouse_id,:parent_id,:code,:name,:location_type,1,:created_at)'), values)
        except IntegrityError:
            raise HTTPException(409, 'Location code exists in warehouse') from None
        r = (await self.session.execute(text('SELECT * FROM inv_locations WHERE id=:id'),
                                        {'id': values['id']})).mappings().first()
        saved = dict(r)
        self._audit('locations', saved['id'], None, saved)
        return saved

    async def list_item_units(self, item_id):
        await self._owned('items', item_id)
        rows = (await self.session.execute(text(
            'SELECT iu.*, u.code AS unit_code FROM inv_item_units iu JOIN inv_units u ON u.id=iu.unit_id'
            ' WHERE iu.item_id=:i'), {'i': item_id})).mappings()
        return {'items': [dict(r) for r in rows]}

    async def add_item_unit(self, item_id, payload):
        item = await self._owned('items', item_id, 'manage')
        unit = await self._reference('inv_units', UUID(str(payload.unit_id)).hex)
        if not item.get('base_unit_id'):
            raise HTTPException(422, 'Define the base unit before alternative units')
        base = await self._reference('inv_units', item['base_unit_id'])
        if unit['dimension'] != base['dimension']:
            raise HTTPException(422, 'Unit dimensions must match')
        if unit['id'] == base['id'] and payload.factor_num != payload.factor_den:
            from decimal import Decimal
            if Decimal(payload.factor_num) != Decimal(payload.factor_den):
                raise HTTPException(422, 'Base unit conversion must equal one')
        from decimal import Decimal as D
        try:
            if D(str(payload.factor_num)) <= 0 or D(str(payload.factor_den)) <= 0:
                raise ValueError()
        except Exception:
            raise HTTPException(422, 'Factors must be positive') from None
        v = {'id': uuid4().hex, 'item_id': item_id, 'unit_id': UUID(str(payload.unit_id)).hex,
             'factor_num': str(payload.factor_num), 'factor_den': str(payload.factor_den),
             'is_purchase': 1 if payload.is_purchase else 0,
             'is_issue': 1 if payload.is_issue else 0, 'created_at': now()}
        try:
            await self.session.execute(text(
                'INSERT INTO inv_item_units (id,item_id,unit_id,factor_num,factor_den,is_purchase,is_issue,created_at)'
                ' VALUES (:id,:item_id,:unit_id,:factor_num,:factor_den,:is_purchase,:is_issue,:created_at)'), v)
        except IntegrityError:
            raise HTTPException(409, 'Unit already linked') from None
        self._audit('item_units', v['id'], None, v)
        return v
