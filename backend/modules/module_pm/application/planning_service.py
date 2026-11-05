"""Planning commands share Core transactions, access, currency, audit and recycle."""
import json
import re
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from core.access import require
from core import soft_delete
from modules.module_currency.application.currency_service import CurrencyService
from modules.module_notifications.application.notification_service import NotificationService
from ..domain.planning import KINDS, cost, total, in_scope
from ..infrastructure.planning_repository import PlanningRepository


def now():
    return datetime.now(timezone.utc).isoformat()


def permission(kind, action):
    return f'pm.projects.{action}' if kind == 'projects' else 'pm.planning.' + ('view' if action == 'view' else 'manage')


class PlanningService:
    def __init__(self, session, request=None):
        self.session, self.request = session, request
        self.repo = PlanningRepository(session)

    async def next_business_code(self, kind, parent=None):
        table, _, code_field, parent_kind, parent_fk = KINDS[kind]
        if kind == 'projects':
            result = await self.session.execute(text('SELECT project_code FROM pm_projects'))
            prefix, pattern = 'P-', r'^P-(\d+)$'
        else:
            parent_code = parent[KINDS[parent_kind][2]]
            prefix, pattern = parent_code + '.', r'^' + re.escape(parent_code + '.') + r'(\d+)$'
            result = await self.session.execute(
                text(f'SELECT {code_field} FROM {table} WHERE {parent_fk}=:parent_id'),
                {'parent_id': parent['id']},
            )
        highest = max(
            (int(match.group(1)) for value in result.scalars()
             if (match := re.fullmatch(pattern, value or ''))),
            default=0,
        )
        width = 3 if kind == 'projects' else 2
        return f'{prefix}{highest + 1:0{width}d}'

    def authorize(self, project, code):
        require(self.request, code)
        if not in_scope(project, self.request.state.user, self.request.state.is_admin,
                        self.request.state.permission_scopes.get(code, {'self'})):
            raise HTTPException(404, 'Project unavailable within assigned scope')

    async def project(self, project_id, code, deleted=False):
        require(self.request, code)
        row = await self.repo.get('projects', project_id)
        if not row or (row['deleted_at'] and not deleted):
            raise HTTPException(404, 'Project unavailable')
        self.authorize(row, code)
        return row

    async def entity(self, kind, project_id, entity_id, action='view', deleted=False):
        project = await self.project(project_id, permission(kind, action), deleted)
        row = project if kind == 'projects' else await self.repo.get(kind, entity_id)
        if not row or (kind != 'projects' and row['project_id'] != project_id) or (row['deleted_at'] and not deleted):
            raise HTTPException(404, 'Planning item unavailable')
        return row

    async def references(self, values):
        org = await self.session.scalar(text('SELECT 1 FROM organizations WHERE id=:id AND is_active=1'), {'id': values['organization_id']})
        manager = await self.session.scalar(text('SELECT 1 FROM users WHERE id=:id AND organization_id=:org AND is_active=1'),
                                           {'id': values['project_manager_user_id'], 'org': values['organization_id']})
        if not org or not manager:
            raise HTTPException(422, 'An active manager in the project organization is required')
        currency = await CurrencyService(self.session).get_rate(values['currency'], values['currency'])
        if currency is None:
            raise HTTPException(422, 'Unknown currency')

    async def snapshot(self, source, destination, rate_date, anchor=None):
        service = CurrencyService(self.session)
        snapshot = (await service.get_anchor_snapshot(source, destination, rate_date, anchor)
                    if anchor else await service.get_rate_snapshot(source, destination, rate_date))
        if not snapshot['available']:
            raise HTTPException(422, 'لا يوجد سعر صرف معتمد مقابل الريال اليمني في تاريخ المصارفة؛ سجّل السعر في جدول العملات وأسعار الصرف.' if anchor else 'No exchange rate available for the planning date')
        snapshot['rate'] = str(snapshot['rate'])
        return json.dumps(snapshot, sort_keys=True)

    async def save(self, kind, project_id, payload, entity_id=None):
        action = 'update' if entity_id else 'create'
        code = permission(kind, action)
        require(self.request, code)
        values = payload.model_dump(mode='json')
        for key in ('organization_id', 'project_manager_user_id', 'phase_id', 'task_id', 'activity_id', 'owner_user_id'):
            if key in values and values[key] is not None:
                values[key] = UUID(values[key]).hex
        before = None
        if entity_id:
            before = await self.entity(kind, project_id, entity_id, action)
            # Older clients do not send additive fields: do not erase them on PUT.
            for key in ('client_name', 'priority', 'owner_user_id', 'description', 'notes', 'attachment_url',
                        'planned_start_date', 'planned_end_date', 'productivity', 'source', 'item_category'):
                if key in values and key not in payload.model_fields_set:
                    values[key] = before[key]
            code_field = KINDS[kind][2]
            if code_field not in payload.model_fields_set:
                values[code_field] = before[code_field]
        entity_id = entity_id or uuid4().hex
        if kind == 'projects':
            if not values.get('project_code'):
                values['project_code'] = await self.next_business_code('projects')
            self.authorize(values, code)
            await self.references(values)
            if before and before['status'] in ('in_progress','completed') and any(before[k]!=values[k] for k in ('organization_id','currency','start_date','daily_hours')):
                raise HTTPException(409,'لا يمكن تغيير إعدادات الخطة بعد بدء التنفيذ')
            if before and before['organization_id']!=values['organization_id'] and await self.repo.children(kind,entity_id):
                raise HTTPException(409,'تغيير منظمة مشروع مخطط يحتاج معالجة ملاك العناصر أولًا')
            if before and before['currency'] != values['currency'] and await self.repo.children(kind, entity_id):
                raise HTTPException(409, 'Project currency is fixed once planning children exist')
        else:
            project = await self.project(project_id, code)
            if project['status'] in ('in_progress','completed'):
                raise HTTPException(409,'الخطة قيد التنفيذ؛ تعديلها يحتاج دورة تغيير معتمدة')
            if values.get('owner_user_id'):
                owner = await self.session.scalar(text(
                    'SELECT 1 FROM users WHERE id=:id AND organization_id=:org AND is_active=1'),
                    {'id': values['owner_user_id'], 'org': project['organization_id']})
                if not owner:
                    raise HTTPException(422, 'Planning owner must be active in the project organization')
            if kind == 'activities' and values.get('planned_start_date') and values.get('planned_end_date'):
                if values['planned_end_date'] < values['planned_start_date']:
                    raise HTTPException(422, 'Planned finish must not precede start')
            values['project_id'] = project_id
            parent_kind, parent_fk = KINDS[kind][3:]
            parent = project if parent_kind == 'projects' else await self.repo.get(parent_kind, values[parent_fk])
            if not parent or parent['deleted_at'] or (parent_kind != 'projects' and parent['project_id'] != project_id):
                raise HTTPException(422, 'Parent must be active in the same project')
            if before and before[parent_fk] != values[parent_fk]:
                raise HTTPException(409, 'Planning parent cannot be changed')
            code_field = KINDS[kind][2]
            if not before and not values.get(code_field):
                values[code_field] = await self.next_business_code(kind, parent)
            if kind in ('activities', 'requirements'):
                if kind == 'activities' and before and before['currency'] != values['currency'] and await self.repo.children(kind, entity_id):
                    raise HTTPException(409, 'Activity currency is fixed once resources exist')
                destination = project['currency'] if kind == 'activities' else parent['currency']
                changed = not before or any(before[k] != values[k] for k in ('currency', 'rate_date'))
                values['exchange_rate_snapshot'] = (await self.snapshot(values['currency'], destination, values['rate_date'], anchor='YER')
                                                    if changed else before['exchange_rate_snapshot'])
        values['updated_at'] = now()
        if before is None:
            values['created_by'] = self.request.state.user_id.hex
            if kind in ('phases','tasks','activities'):
                fk=KINDS[kind][4]
                siblings=[r for r in await self.repo.rows(kind,project_id) if not r['deleted_at'] and r[fk]==values[fk]]
                values['sort_order']=max((r['sort_order'] for r in siblings),default=-1)+1
        try:
            await self.repo.save(kind, entity_id, values, create=before is None)
        except IntegrityError:
            raise HTTPException(409, 'Business code already exists or a referenced item is unavailable') from None
        after = await self.repo.get(kind, entity_id)
        if kind in ('activities','requirements'):
            activity_id = entity_id if kind=='activities' else values['activity_id']
            if before is None or any(before.get(k)!=v for k,v in values.items() if k not in ('updated_at','created_by')):
                await self.repo.save('activities',activity_id,{'approval_status':'pending','approval_reason':'تغيرت بيانات التخطيط',
                    'approved_by':None,'approved_at':None})
                if kind=='activities': after=await self.repo.get(kind,entity_id)
        self.audit(kind, entity_id, before, after)
        if kind == 'projects' and (before is None or before['project_manager_user_id'] != after['project_manager_user_id']):
            await NotificationService(self.session).emit('pm.project_assigned', UUID(after['project_manager_user_id']),
                {'project': after['name']}, 'pm.assignment.' + uuid4().hex, 'pm.projects', UUID(entity_id))
        return await self.present(kind, after)

    def audit(self, kind, entity_id, before, after):
        self.request.state.audit_details = {'entity_type': 'pm.' + kind, 'entity_id': str(UUID(entity_id)),
            'old': before, 'new': after, 'summary': 'PM planning ' + kind}

    async def delete(self, kind, project_id, entity_id):
        row = await self.entity(kind, project_id, entity_id, 'delete')
        project = row if kind=='projects' else await self.repo.get('projects',project_id)
        if project['status'] in ('in_progress','completed'):
            raise HTTPException(409,'لا يمكن حذف خطة مشروع قيد التنفيذ')
        if await self.repo.children(kind, entity_id, active_only=True):
            raise HTTPException(409, 'Delete active children first')
        if kind == 'activities' and await self.session.scalar(text(
            'SELECT 1 FROM pm_work_orders w '
            'WHERE w.project_id=:project_id AND w.activity_id=:activity_id AND ('
            'CAST(w.actual_quantity_snapshot AS NUMERIC) != 0 '
            'OR EXISTS (SELECT 1 FROM pm_execution_quantity_events e '
            'WHERE e.work_order_id=w.id AND e.project_id=w.project_id) '
            'OR EXISTS (SELECT 1 FROM pm_work_order_consumptions c '
            'WHERE c.work_order_id=w.id AND c.project_id=w.project_id)) LIMIT 1'),
            {'project_id': project_id, 'activity_id': entity_id}):
            raise HTTPException(409, 'لا يمكن حذف النشاط لوجود تنفيذ فعلي مسجل مرتبط به')
        await self.repo.save(kind, entity_id, {'deleted_at': now(), 'deleted_by': self.request.state.user_id.hex})
        bin_id = await soft_delete.soft_delete(self.session, 'pm.' + kind, UUID(entity_id), self.request.state.user_id,
            metadata={'label': row['name']})
        self.audit(kind, entity_id, row, await self.repo.get(kind, entity_id))
        if kind=='requirements':
            await self.repo.save('activities',row['activity_id'],{'approval_status':'pending','approval_reason':'حذف احتياج',
                'approved_by':None,'approved_at':None})
        return {'deleted': True, 'recycle_id': bin_id}

    async def recover(self, kind, entity_id, actor_id, purge=False):
        row = await self.repo.get(kind, entity_id)
        if not row or not row['deleted_at']:
            raise HTTPException(409, 'Item is not deleted')
        project = row if kind=='projects' else await self.repo.get('projects',row['project_id'])
        if project and project['status'] in ('in_progress','completed'):
            raise HTTPException(409,'لا يمكن تغيير خطة مشروع قيد التنفيذ عبر سلة المحذوفات')
        if purge:
            if await self.repo.children(kind, entity_id):
                raise HTTPException(409, 'Purge children first')
            await self.session.execute(text(f'DELETE FROM {KINDS[kind][0]} WHERE id=:id'), {'id': entity_id})
            return
        if kind != 'projects':
            parent_kind, fk = KINDS[kind][3:]
            parent = await self.repo.get(parent_kind, row[fk])
            project = await self.repo.get('projects', row['project_id'])
            if not parent or parent['deleted_at'] or not project or project['deleted_at']:
                raise HTTPException(409, 'Restore the project and parent first')
        await self.repo.save(kind, entity_id, {'deleted_at': None, 'deleted_by': None,
                                               'restored_by': UUID(str(actor_id)).hex, 'updated_at': now()})
        if kind in ('activities','requirements'):
            await self.repo.save('activities',entity_id if kind=='activities' else row['activity_id'],
                {'approval_status':'pending','approval_reason':'استعادة بيانات التخطيط','approved_by':None,'approved_at':None})

    async def present(self, kind, row):
        result = dict(row)
        if kind=='projects':
            result['manager_name']=await self.session.scalar(text('SELECT full_name FROM users WHERE id=:id'),{'id':row['project_manager_user_id']})
        if row.get('owner_user_id'):
            result['owner_name'] = await self.session.scalar(text('SELECT full_name FROM users WHERE id=:id'), {'id':row['owner_user_id']})
        if kind == 'requirements':
            snapshot = json.loads(row['exchange_rate_snapshot'])
            result['planned_cost'] = str(cost(row['quantity'], row['unit_price'], snapshot['rate']))
            result['planned_cost_currency'] = snapshot['to']
            result['exchange_rate_snapshot'] = snapshot
        elif kind == 'activities':
            resources = [r for r in await self.repo.rows('requirements', row['project_id']) if r['activity_id'] == row['id'] and not r['deleted_at']]
            result['planned_cost'] = str(total(cost(r['quantity'], r['unit_price'], json.loads(r['exchange_rate_snapshot'])['rate']) for r in resources))
            result['exchange_rate_snapshot'] = json.loads(row['exchange_rate_snapshot'])
        else:
            pid = row['id'] if kind == 'projects' else row['project_id']
            phases = {r['id'] for r in await self.repo.rows('phases', pid) if not r['deleted_at'] and (kind != 'phases' or r['id'] == row['id'])}
            tasks = {r['id'] for r in await self.repo.rows('tasks', pid) if not r['deleted_at'] and r['phase_id'] in phases and (kind != 'tasks' or r['id'] == row['id'])}
            activities = [r for r in await self.repo.rows('activities', pid) if not r['deleted_at'] and r['task_id'] in tasks]
            presented = [await self.present('activities', r) for r in activities]
            for field in ('planned_quantity', 'planned_duration'):
                result[field] = str(total(r[field] for r in activities))
            result['planned_cost'] = str(total(cost(r['planned_cost'], 1, r['exchange_rate_snapshot']['rate']) for r in presented))
            result['currency'] = (await self.repo.get('projects', pid))['currency']
        return result
