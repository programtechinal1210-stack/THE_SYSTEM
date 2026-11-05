"""Fixed-table SQL repository. No table/column identifiers come from clients."""
from sqlalchemy import text
from fastapi import HTTPException
from ..domain.catalog import KINDS


class InventoryRepository:
    def __init__(self, session):
        self.session = session

    async def get(self, kind, entity_id):
        result = await self.session.execute(
            text(f'SELECT * FROM {KINDS[kind][0]} WHERE id=:id'), {'id': entity_id})
        row = result.mappings().first()
        return dict(row) if row else None

    async def list(self, kind, organization_id=None, search=None, skip=0, limit=50,
                   category_id=None, is_active=None, item_type=None):
        table = KINDS[kind][0]
        org_scoped = KINDS[kind][5]
        sql = f'SELECT * FROM {table} WHERE deleted_at IS NULL'
        params = {}
        if org_scoped:
            sql += ' AND organization_id=:org'
            params['org'] = organization_id
        if search:
            name = 'name_ar' if kind in ('items', 'categories') else 'name'
            detail_search=''
            if kind=='items':
                columns=(await self.session.execute(text('PRAGMA table_info(inv_items)'))).mappings().all()
                if 'aliases_json' in {c['name'] for c in columns}:
                    detail_search=' OR barcode LIKE :s OR aliases_json LIKE :s'
            sql += f' AND (code LIKE :s OR {name} LIKE :s{detail_search})'
            params['s'] = f'%{search}%'
        if kind == 'items':
            if category_id:
                sql += ' AND category_id=:category_id'
                params['category_id'] = category_id
            if is_active is not None:
                sql += ' AND is_active=:is_active'
                params['is_active'] = int(is_active)
            if item_type:
                sql += ' AND item_type=:item_type'
                params['item_type'] = item_type
        sql += ' ORDER BY created_at,id LIMIT :l OFFSET :o'
        params.update({'l': min(limit, 200), 'o': max(skip, 0)})
        rows = (await self.session.execute(text(sql), params)).mappings()
        return [dict(r) for r in rows]

    async def save(self, kind, entity_id, values, create=False):
        table = KINDS[kind][0]
        if kind=='items':
            columns={c['name'] for c in (await self.session.execute(text('PRAGMA table_info(inv_items)'))).mappings()}
            if not set(values).issubset(columns):
                raise HTTPException(409,'SETUP_MIGRATION_REQUIRED')
        if create:
            values = dict(values, id=entity_id)
            cols = list(values.keys())
            col_list = ",".join(cols)
            val_list = ",".join(":" + k for k in cols)
            sql = f'INSERT INTO {table} ({col_list}) VALUES ({val_list})'
            await self.session.execute(text(sql), {k: values[k] for k in cols})
            await self.session.flush()
        else:
            cols = [k for k in values if k != 'id']
            set_list = ",".join(f'{k}=:{k}' for k in cols)
            sql = f'UPDATE {table} SET {set_list} WHERE id=:id'
            await self.session.execute(text(sql), {**{k: values[k] for k in cols}, 'id': entity_id})
            await self.session.flush()
