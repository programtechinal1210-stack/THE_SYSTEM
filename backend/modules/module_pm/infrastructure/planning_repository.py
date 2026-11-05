"""Fixed-table SQL repository. No table/column identifiers come from clients."""
from sqlalchemy import text
from ..domain.planning import KINDS


class PlanningRepository:
    def __init__(self, session):
        self.session = session

    async def get(self, kind, entity_id):
        result = await self.session.execute(text(f'SELECT * FROM {KINDS[kind][0]} WHERE id=:id'), {'id': entity_id})
        row = result.mappings().first()
        return dict(row) if row else None

    async def rows(self, kind, project_id=None):
        sql = f'SELECT * FROM {KINDS[kind][0]}'
        if project_id is not None:
            sql += ' WHERE project_id=:pid'
        order = 'sort_order,created_at,id' if kind in ('phases','tasks','activities') else 'created_at,id'
        result = await self.session.execute(text(sql + ' ORDER BY ' + order), {'pid': project_id})
        return [dict(r) for r in result.mappings()]

    async def save(self, kind, entity_id, values, create=False):
        table = KINDS[kind][0]
        if create:
            values = dict(values, id=entity_id)
            sql = f'INSERT INTO {table} ({",".join(values)}) VALUES ({",".join(":"+k for k in values)})'
        else:
            sql = f'UPDATE {table} SET ' + ','.join(f'{k}=:{k}' for k in values) + ' WHERE id=:id'
            values = dict(values, id=entity_id)
        await self.session.execute(text(sql), values)

    async def children(self, kind, entity_id, active_only=False):
        for child, (_, _, _, parent, fk) in KINDS.items():
            if parent == kind:
                suffix = ' AND deleted_at IS NULL' if active_only else ''
                return bool(await self.session.scalar(text(f'SELECT 1 FROM {KINDS[child][0]} WHERE {fk}=:id{suffix} LIMIT 1'), {'id': entity_id}))
        return False
