"""Reference invariants shared by writes and recycle restoration."""
from fastapi import HTTPException
from sqlalchemy import text


class CatalogValidation:
    async def _protect_stock(self, field, identifier):
        from decimal import Decimal, InvalidOperation
        if field not in ('item_id', 'warehouse_id', 'location_id'):
            raise ValueError('Invalid stock reference field')
        installed = await self.session.scalar(text("SELECT 1 FROM sqlite_master WHERE name='inv_stock_balances'"))
        if not installed:
            return
        values = (await self.session.execute(text(f'SELECT quantity_on_hand FROM inv_stock_balances WHERE {field}=:i'), {'i': identifier})).scalars()
        for value in values:
            try:
                nonzero = Decimal(value) != 0
            except InvalidOperation:
                nonzero = True
            if nonzero:
                raise HTTPException(409, 'Entity has stock; settle its balance before deletion')

    async def _reference(self, table, identifier):
        row = (await self.session.execute(text(f'SELECT * FROM {table} WHERE id=:id'),
                                          {'id': identifier})).mappings().first()
        if not row or row.get('deleted_at') or not row.get('is_active', True):
            raise HTTPException(422, 'Reference unavailable')
        return dict(row)

    async def _parent(self, table, parent_id, identifier, scope_field, scope):
        seen = {identifier}
        while parent_id:
            if parent_id in seen:
                raise HTTPException(422, 'Hierarchy cycle is not allowed')
            seen.add(parent_id)
            parent = await self._reference(table, parent_id)
            if parent[scope_field] != scope or parent.get('status', 'active') != 'active':
                raise HTTPException(422, 'Parent is outside the active reference scope')
            parent_id = parent.get('parent_id')

    async def _validate(self, kind, values, identifier):
        org = values.get('organization_id')
        if org:
            await self._check_org(org)
        if kind in ('categories', 'warehouses'):
            await self._parent('inv_' + kind, values.get('parent_id'), identifier, 'organization_id', org)
        if kind == 'items':
            old = await self.repo.get('items', identifier)
            if old and values.get('base_unit_id') != old['base_unit_id']:
                requested = await self.session.scalar(text("SELECT 1 FROM sqlite_master WHERE name='inv_request_lines'"))
                if requested and await self.session.scalar(text('SELECT 1 FROM inv_request_lines WHERE item_id=:i LIMIT 1'),{'i':identifier}):
                    raise HTTPException(409,'Base unit is fixed by material request history')
                installed = await self.session.scalar(text("SELECT 1 FROM sqlite_master WHERE name='inv_document_lines'"))
                if installed and await self.session.scalar(text('SELECT 1 FROM inv_document_lines WHERE item_id=:i LIMIT 1'), {'i': identifier}):
                    raise HTTPException(409, 'Base unit is fixed by inventory document history')
            if values.get('category_id'):
                category = await self._reference('inv_categories', values['category_id'])
                if category['organization_id'] != org:
                    raise HTTPException(422, 'Category must belong to the item organization')
            if values.get('base_unit_id'):
                base = await self._reference('inv_units', values['base_unit_id'])
                links = (await self.session.execute(text(
                    'SELECT u.dimension FROM inv_item_units iu JOIN inv_units u ON u.id=iu.unit_id WHERE iu.item_id=:i'),
                    {'i': identifier})).scalars().all()
                if any(d != base['dimension'] for d in links):
                    raise HTTPException(422, 'Base unit conflicts with linked dimensions')
            if values.get('tracking_policy', 'none') != 'none':
                raise HTTPException(422, 'Lot and serial tracking engines are not enabled')
        if kind == 'units':
            old = await self.repo.get('units', identifier)
            if old and any(values.get(k, old[k]) != old[k] for k in ('dimension', 'precision')):
                await self._unit_unused(identifier)
        if kind == 'warehouses':
            dept = values.get('operating_department_id')
            if dept:
                seen = set()
                current = dept
                while current and current not in seen:
                    seen.add(current)
                    row = await self._reference('organizations', current)
                    if current == org:
                        break
                    current = row.get('parent_id')
                else:
                    raise HTTPException(422, 'Operating department must belong to organization hierarchy')
            if values.get('manager_user_id'):
                user = await self._reference('users', values['manager_user_id'])
                if user['organization_id'] not in (org, dept):
                    raise HTTPException(422, 'Manager must belong to the warehouse organization or operating department')

    async def _unit_unused(self, identifier):
        for table, field in (('inv_items', 'base_unit_id'), ('inv_item_units', 'unit_id')):
            if await self.session.scalar(text(f'SELECT 1 FROM {table} WHERE {field}=:i LIMIT 1'), {'i': identifier}):
                raise HTTPException(409, 'Unit is referenced by inventory history')
        installed = await self.session.scalar(text("SELECT 1 FROM sqlite_master WHERE name='inv_document_lines'"))
        if installed and await self.session.scalar(text('SELECT 1 FROM inv_document_lines WHERE unit_id=:i LIMIT 1'), {'i': identifier}):
            raise HTTPException(409, 'Unit is referenced by inventory documents')

    async def _owned(self, kind, identifier, action='view'):
        from .inventory_service import permission, in_scope
        from core.access import require
        code = permission(kind, action)
        require(self.request, code)
        row = await self.repo.get(kind, identifier)
        if not row or row.get('deleted_at') or not self._allows_org(row, code):
            raise HTTPException(404, 'Inventory record unavailable within scope')
        return row
