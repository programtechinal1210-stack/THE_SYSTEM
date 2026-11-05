"""Governance/control: risks, deviations, cash flow, communications, daily reports."""
import json
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from core import soft_delete
from .planning_service import PlanningService, now
from ..domain.control import CONTROL_KINDS

UUID_KEYS = ('phase_id', 'task_id', 'activity_id', 'owner_user_id',
             'responsible_user_id', 'sender_user_id')
REF_TABLES = {'phase_id': 'pm_phases', 'task_id': 'pm_tasks', 'activity_id': 'pm_activities'}


def control_permission(kind, action):
    if kind == 'risks':
        return 'pm.risks.view' if action == 'view' else 'pm.risks.manage'
    if kind == 'reports' and action == 'view':
        return 'pm.reports.view'
    return 'pm.planning.view' if action == 'view' else 'pm.planning.manage'


class ControlService(PlanningService):
    def table(self, kind):
        return CONTROL_KINDS[kind][0]

    def code_col(self, kind):
        return CONTROL_KINDS[kind][2]

    async def _row(self, kind, entity_id, project_id=None):
        where = 'id=:id' if project_id is None else 'id=:id AND project_id=:p'
        params = {'id': entity_id} if project_id is None else {'id': entity_id, 'p': project_id}
        r = (await self.session.execute(text(f'SELECT * FROM {self.table(kind)} WHERE {where}'), params)).mappings().first()
        return dict(r) if r else None

    async def _validate_refs(self, project_id, values):
        project = await self.repo.get('projects', project_id)
        for fk, table in REF_TABLES.items():
            if values.get(fk):
                ok = await self.session.scalar(text(
                    f'SELECT 1 FROM {table} WHERE id=:id AND project_id=:p AND deleted_at IS NULL'),
                    {'id': values[fk], 'p': project_id})
                if not ok:
                    raise HTTPException(422, 'Scope reference must belong to this project')
        if values.get('task_id') and values.get('phase_id'):
            task = (await self.session.execute(text(
                'SELECT phase_id FROM pm_tasks WHERE id=:id AND project_id=:p AND deleted_at IS NULL'),
                {'id': values['task_id'], 'p': project_id})).mappings().first()
            if task and task['phase_id'] != values['phase_id']:
                raise HTTPException(422, 'Risk hierarchy references must follow the same parent chain')
        if values.get('activity_id'):
            activity = (await self.session.execute(text(
                'SELECT task_id FROM pm_activities WHERE id=:id AND project_id=:p AND deleted_at IS NULL'),
                {'id': values['activity_id'], 'p': project_id})).mappings().first()
            if activity and values.get('task_id') and activity['task_id'] != values['task_id']:
                raise HTTPException(422, 'Risk hierarchy references must follow the same parent chain')
            if activity and values.get('phase_id'):
                task = (await self.session.execute(text(
                    'SELECT phase_id FROM pm_tasks WHERE id=:id AND project_id=:p AND deleted_at IS NULL'),
                    {'id': activity['task_id'], 'p': project_id})).mappings().first()
                if task and task['phase_id'] != values['phase_id']:
                    raise HTTPException(422, 'Risk hierarchy references must follow the same parent chain')
        if values.get('owner_user_id'):
            owner = await self.session.scalar(text(
                'SELECT 1 FROM users WHERE id=:id AND is_active=1 AND organization_id=:org'),
                {'id': values['owner_user_id'], 'org': project['organization_id']})
            if not owner:
                raise HTTPException(422, 'Risk owner must be active in the project organization')
        for user_fk in ('owner_user_id', 'responsible_user_id', 'sender_user_id'):
            if user_fk == 'owner_user_id':
                continue
            if values.get(user_fk):
                ok = await self.session.scalar(text(
                    'SELECT 1 FROM users WHERE id=:id AND is_active=1'), {'id': values[user_fk]})
                if not ok:
                    raise HTTPException(422, 'Referenced user must be active')

    async def list(self, kind, project_id, q=''):
        await self.project(project_id, control_permission(kind, 'view'))
        rows = (await self.session.execute(text(
            f'SELECT * FROM {self.table(kind)} WHERE project_id=:p AND deleted_at IS NULL ORDER BY created_at'),
            {'p': project_id})).mappings()
        items = [await self.present(kind, dict(r)) for r in rows]
        if q:
            items = [i for i in items if q.casefold() in (i.get('name', '') + ' ' + i.get(self.code_col(kind), '')).casefold()]
        return {'items': items}

    async def detail(self, kind, project_id, entity_id):
        await self.project(project_id, control_permission(kind, 'view'))
        row = await self._row(kind, entity_id, project_id)
        if not row or row['deleted_at']:
            raise HTTPException(404, 'Control item unavailable')
        return await self.present(kind, row)

    async def save(self, kind, project_id, payload, entity_id=None):
        await self.project(project_id, control_permission(kind, 'update' if entity_id else 'create'))
        values = payload.model_dump(mode='json')
        for key in UUID_KEYS:
            if key in values:
                values[key] = UUID(values[key]).hex if values[key] else None
        values['name'] = values[self.code_col(kind)]
        values['project_id'] = project_id
        await self._validate_refs(project_id, values)
        if kind == 'risks':
            values['importance'] = str(Decimal(str(payload.probability)) * Decimal(payload.impact))
        if kind == 'cashflows':
            project = await self.repo.get('projects', project_id)
            values['exchange_rate_snapshot'] = await self.snapshot(
                payload.currency, project['currency'], payload.rate_date.isoformat())
        values['updated_at'] = now()
        if entity_id is None:
            values['created_by'] = self.request.state.user_id.hex
            if kind == 'reports':
                values['prepared_by'] = self.request.state.user_id.hex
            values['id'] = entity_id = uuid4().hex
            sql = f'INSERT INTO {self.table(kind)} ({",".join(values)}) VALUES ({",".join(":" + k for k in values)})'
        else:
            before = await self._row(kind, entity_id, project_id)
            if not before or before['deleted_at']:
                raise HTTPException(404, 'Control item unavailable')
            values['id'] = entity_id
            sql = f'UPDATE {self.table(kind)} SET ' + ','.join(f'{k}=:{k}' for k in values) + ' WHERE id=:id'
        try:
            await self.session.execute(text(sql), values)
        except IntegrityError:
            raise HTTPException(409, 'Business code already exists') from None
        row = await self._row(kind, entity_id)
        self.request.state.audit_details = {'entity_type': 'pm.' + kind, 'entity_id': str(UUID(entity_id)),
                                            'old': None, 'new': row, 'summary': 'PM control ' + kind}
        return await self.present(kind, row)

    async def present(self, kind, row):
        result = dict(row)
        if kind == 'reports':
            result['volume_deviation'] = str(Decimal(row['executed_volume']) - Decimal(row['planned_volume']))
        if kind == 'cashflows':
            snap = json.loads(row['exchange_rate_snapshot'])
            result['amount_converted'] = str(Decimal(row['amount']) * Decimal(snap['rate']))
            result['currency'] = snap['to']
            result['exchange_rate_snapshot'] = snap
        return result

    async def delete(self, kind, project_id, entity_id):
        await self.project(project_id, control_permission(kind, 'manage'))
        row = await self._row(kind, entity_id, project_id)
        if not row or row['deleted_at']:
            raise HTTPException(404, 'Control item unavailable')
        await self.session.execute(text(
            f'UPDATE {self.table(kind)} SET deleted_at=:t, deleted_by=:b, updated_at=:t WHERE id=:id'),
            {'t': now(), 'b': self.request.state.user_id.hex, 'id': entity_id})
        bin_id = await soft_delete.soft_delete(self.session, 'pm.' + kind, UUID(entity_id),
                                               self.request.state.user_id, metadata={'label': row['name']})
        self.request.state.audit_details = {'entity_type': 'pm.' + kind, 'entity_id': str(UUID(entity_id)),
                                            'old': row, 'new': {'deleted': True}, 'summary': 'PM control delete'}
        return {'deleted': True, 'recycle_id': bin_id}

    async def recover(self, kind, entity_id, actor_id, purge=False):
        row = await self._row(kind, entity_id)
        if not row or not row['deleted_at']:
            raise HTTPException(409, 'Item is not deleted')
        if purge:
            await self.session.execute(text(f'DELETE FROM {self.table(kind)} WHERE id=:id'), {'id': entity_id})
            return
        project = await self.repo.get('projects', row['project_id'])
        if not project or project['deleted_at']:
            raise HTTPException(409, 'Restore the project first')
        await self.session.execute(text(
            f'UPDATE {self.table(kind)} SET deleted_at=NULL, deleted_by=NULL, restored_by=:b, updated_at=:t WHERE id=:id'),
            {'b': UUID(str(actor_id)).hex, 't': now(), 'id': entity_id})

    async def set_status(self, kind, project_id, entity_id, target):
        if kind == 'reports' and target in ('approved', 'rejected'):
            await self.project(project_id, 'pm.projects.update')
        else:
            await self.project(project_id, control_permission(kind, 'manage'))
        row = await self._row(kind, entity_id, project_id)
        if not row or row['deleted_at']:
            raise HTTPException(404, 'Control item unavailable')
        allowed = {'risks': {'active': {'closed'}, 'closed': {'active'}},
                   'deviations': {'open': {'closed'}, 'closed': {'open'}},
                   'reports': {'draft': {'submitted'}, 'submitted': {'approved', 'rejected'}}}
        if target == row['status'] or target not in allowed[kind].get(row['status'], set()):
            raise HTTPException(409, 'Invalid status transition')
        updates = {'status': target, 'updated_at': now()}
        if kind == 'risks':
            updates['closure_date'] = now() if target == 'closed' else None
        if kind == 'deviations':
            updates['actual_date'] = now() if target == 'closed' else None
        if kind == 'reports' and target == 'approved':
            updates['approved_by'] = self.request.state.user_id.hex
            updates['approved_at'] = now()
        await self.session.execute(text(
            f'UPDATE {self.table(kind)} SET ' + ','.join(f'{k}=:{k}' for k in updates) + ' WHERE id=:id'),
            dict(updates, id=entity_id))
        row = await self._row(kind, entity_id)
        self.request.state.audit_details = {'entity_type': 'pm.' + kind, 'entity_id': str(UUID(entity_id)),
                                            'old': {'status': 'previous'}, 'new': {'status': target},
                                            'summary': 'PM control status change'}
        return await self.present(kind, row)
