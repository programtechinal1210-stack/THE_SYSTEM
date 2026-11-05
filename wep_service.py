"""Weekly Execution Plan (WEP): plans, items, baselines, history, closure, carryover."""
import json
from decimal import Decimal, ROUND_HALF_EVEN
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from .planning_service import PlanningService, now

WEP_TRANSITIONS = {
    'draft': {'review', 'cancelled'},
    'review': {'approved', 'draft', 'cancelled'},
    'approved': {'in_progress', 'reopened'},
    'in_progress': {'reopened'},
    'closed': {'reopened'},
    'reopened': {'review', 'cancelled'},
    'cancelled': set(),
}
EDITABLE = ('draft', 'reopened')


class WepService(PlanningService):
    async def _plan(self, plan_id, project_id):
        row = (await self.session.execute(text(
            'SELECT * FROM pm_weekly_plans WHERE id=:id AND project_id=:p'),
            {'id': plan_id, 'p': project_id})).mappings().first()
        if not row or row['deleted_at']:
            raise HTTPException(404, 'Weekly plan unavailable')
        return dict(row)

    async def _items(self, plan_id):
        rows = (await self.session.execute(text(
            'SELECT * FROM pm_weekly_plan_items WHERE plan_id=:p AND deleted_at IS NULL ORDER BY created_at'),
            {'p': plan_id})).mappings()
        return [dict(r) for r in rows]

    async def _actual_quantity(self, project_id, activity_id, start, end):
        rows = (await self.session.execute(text(
            "SELECT e.id,e.delta,e.recorded_at,e.work_order_id FROM pm_execution_quantity_events e "
            "JOIN pm_work_orders w ON w.id=e.work_order_id AND w.project_id=e.project_id "
            "WHERE e.project_id=:p AND e.activity_id=:a AND w.deleted_at IS NULL "
            "AND w.status != 'rejected' AND substr(e.recorded_at,1,10) BETWEEN :s AND :e ORDER BY e.recorded_at,e.id"),
            {'p':project_id,'a':activity_id,'s':start,'e':end})).mappings().all()
        evidence = [{'source':'pm_execution_quantity_events','id':r['id'],'quantity':r['delta'],
                     'recorded_at':r['recorded_at'],'work_order_id':r['work_order_id']} for r in rows]
        undated = await self.session.scalar(text(
            "SELECT count(*) FROM pm_work_orders w WHERE w.project_id=:p AND w.activity_id=:a "
            "AND w.deleted_at IS NULL AND w.status != 'rejected' AND CAST(w.actual_quantity_snapshot AS NUMERIC) != 0 "
            "AND NOT EXISTS (SELECT 1 FROM pm_execution_quantity_events e WHERE e.work_order_id=w.id)"),
            {'p':project_id,'a':activity_id})
        return sum((Decimal(r['delta']) for r in rows),Decimal(0)), evidence, bool(undated)

    async def list_plans(self, project_id):
        await self.project(project_id, 'pm.wep.view')
        rows = (await self.session.execute(text(
            'SELECT * FROM pm_weekly_plans WHERE project_id=:p AND deleted_at IS NULL ORDER BY start_date'),
            {'p': project_id})).mappings()
        return {'items': [dict(r) for r in rows]}

    async def create_plan(self, project_id, payload):
        await self.project(project_id, 'pm.wep.manage')
        values = payload.model_dump(mode='json')
        values['name'] = values['week_code']
        values['project_id'] = project_id
        values['created_by'] = self.request.state.user_id.hex
        values['id'] = uuid4().hex
        values['updated_at'] = now()
        try:
            await self.session.execute(text(
                'INSERT INTO pm_weekly_plans (id,name,created_by,updated_at,project_id,week_code,start_date,end_date) '
                'VALUES (:id,:name,:created_by,:updated_at,:project_id,:week_code,:start_date,:end_date)'), values)
        except IntegrityError:
            raise HTTPException(409, 'Week code already exists') from None
        return await self._plan(values['id'], project_id)

    async def detail_plan(self, project_id, plan_id):
        await self.project(project_id, 'pm.wep.view')
        plan = await self._plan(plan_id, project_id)
        if plan['status'] == 'closed' and plan['closure']:
            return {**plan, 'items':json.loads(plan['closure'])['items'], 'frozen':True}
        items = []
        for it in await self._items(plan_id):
            actual, evidence, undated = await self._actual_quantity(project_id,it['activity_id'],plan['start_date'],plan['end_date'])
            it.update(actual=str(actual),evidence=evidence,undated_actual=undated)
            items.append(it)
        return {**plan, 'items': items}

    async def add_item(self, project_id, plan_id, payload):
        await self.project(project_id, 'pm.wep.manage')
        plan = await self._plan(plan_id, project_id)
        if plan['status'] not in EDITABLE:
            raise HTTPException(409, 'Plan is not editable in its current status')
        act = await self.repo.get('activities', payload.activity_id.hex)
        if not act or act['project_id'] != project_id or act['deleted_at']:
            raise HTTPException(422, 'Activity must belong to this project and be active')
        values = payload.model_dump(mode='json')
        values['activity_id'] = UUID(values['activity_id']).hex
        values['assignee_user_id'] = UUID(values['assignee_user_id']).hex if values.get('assignee_user_id') else None
        values['name'] = values['activity_id']
        values['project_id'] = project_id
        values['plan_id'] = plan_id
        values['created_by'] = self.request.state.user_id.hex
        values['id'] = uuid4().hex
        values['updated_at'] = now()
        try:
            await self.session.execute(text(
                'INSERT INTO pm_weekly_plan_items (id,name,created_by,updated_at,project_id,plan_id,activity_id,weekly_target,assignee_user_id) '
                'VALUES (:id,:name,:created_by,:updated_at,:project_id,:plan_id,:activity_id,:weekly_target,:assignee_user_id)'), values)
        except IntegrityError:
            raise HTTPException(409, 'Activity already planned in this week') from None
        item = (await self.session.execute(text(
            'SELECT * FROM pm_weekly_plan_items WHERE id=:id'), {'id': values['id']})).mappings().first()
        return dict(item)

    async def _log(self, plan_id, project_id, event, note=''):
        await self.session.execute(text(
            'INSERT INTO pm_weekly_plan_history (id, plan_id, project_id, event, actor, note) '
            'VALUES (:id, :plan, :p, :event, :actor, :note)'),
            {'id': uuid4().hex, 'plan': plan_id, 'p': project_id, 'event': event,
             'actor': self.request.state.user_id.hex, 'note': note})

    async def update_item(self, project_id, plan_id, item_id, payload):
        await self.project(project_id, 'pm.wep.manage')
        plan = await self._plan(plan_id, project_id)
        if plan['status'] not in EDITABLE:
            raise HTTPException(409, 'Plan is not editable in its current status')
        before = (await self.session.execute(text(
            'SELECT * FROM pm_weekly_plan_items WHERE id=:id AND plan_id=:plan AND project_id=:p AND deleted_at IS NULL'),
            {'id':item_id,'plan':plan_id,'p':project_id})).mappings().first()
        if not before:
            raise HTTPException(404, 'Weekly commitment unavailable')
        assignee = payload.assignee_user_id.hex if payload.assignee_user_id else None
        if assignee and not await self.session.scalar(text('SELECT 1 FROM users WHERE id=:id AND is_active=1'),{'id':assignee}):
            raise HTTPException(422, 'Referenced user must be active')
        values = {'target':str(payload.weekly_target),'assignee':assignee,'at':now(),'id':item_id}
        await self.session.execute(text(
            'UPDATE pm_weekly_plan_items SET weekly_target=:target,assignee_user_id=:assignee,updated_at=:at WHERE id=:id'),values)
        await self._log(plan_id,project_id,'item:updated',note=item_id)
        self.request.state.audit_details = {'entity_type':'pm.weekly_plan_items','entity_id':str(UUID(item_id)),
            'old':dict(before),'new':payload.model_dump(mode='json'),'summary':'PM weekly commitment updated'}
        return {'id':item_id,'weekly_target':str(payload.weekly_target),'assignee_user_id':assignee}

    async def transition(self, project_id, plan_id, target, reason=''):
        await self.project(project_id, 'pm.wep.manage')
        plan = await self._plan(plan_id, project_id)
        if target not in WEP_TRANSITIONS.get(plan['status'], set()):
            raise HTTPException(409, 'Invalid weekly plan transition')
        if target == 'reopened' and (not reason.strip() or plan['carried_over']):
            raise HTTPException(409, 'Reopening requires a reason and no prior carryover')
        if target in ('review','approved'):
            items = await self._items(plan_id)
            if not items or any(Decimal(i['weekly_target']) <= 0 for i in items):
                raise HTTPException(409, 'Review requires positive commitments')
        updates = {'status': target, 'updated_at': now()}
        await self.session.execute(text(
            'UPDATE pm_weekly_plans SET ' + ','.join(f'{k}=:{k}' for k in updates) + ' WHERE id=:id'),
            dict(updates, id=plan_id))
        await self._log(plan_id, project_id, 'status:' + target, note=reason)
        if target == 'approved':
            await self._baseline(plan_id, project_id)
        self.request.state.audit_details = {'entity_type': 'pm.weekly_plans', 'entity_id': str(UUID(plan_id)),
                                            'old': {'status': plan['status']}, 'new': {'status': target},
                                            'summary': 'PM weekly plan status change'}
        return await self._plan(plan_id, project_id)

    async def _baseline(self, plan_id, project_id):
        items = [{'activity_id': it['activity_id'], 'weekly_target': it['weekly_target'],
                  'assignee_user_id': it['assignee_user_id']} for it in await self._items(plan_id)]
        current = await self.session.scalar(text(
            'SELECT COALESCE(MAX(version),0) FROM pm_weekly_plan_baselines WHERE plan_id=:p'), {'p': plan_id})
        version = (current or 0) + 1
        await self.session.execute(text(
            'INSERT INTO pm_weekly_plan_baselines (id, plan_id, project_id, version, approved_by, snapshot) '
            'VALUES (:id, :plan, :p, :v, :by, :snap)'),
            {'id': uuid4().hex, 'plan': plan_id, 'p': project_id, 'v': version,
             'by': self.request.state.user_id.hex, 'snap': json.dumps(items, sort_keys=True)})

    async def baselines(self, project_id, plan_id):
        await self.project(project_id, 'pm.wep.view')
        await self._plan(plan_id, project_id)
        rows = (await self.session.execute(text(
            'SELECT * FROM pm_weekly_plan_baselines WHERE plan_id=:p ORDER BY version DESC'),
            {'p': plan_id})).mappings()
        return {'items': [dict(r) for r in rows]}

    async def close_week(self, project_id, plan_id):
        await self.project(project_id, 'pm.wep.manage')
        plan = await self._plan(plan_id, project_id)
        if plan['status'] != 'in_progress':
            raise HTTPException(409, 'Only an in-progress week can be closed')
        results = []
        total_target = Decimal('0')
        total_actual = Decimal('0')
        baseline = (await self.session.execute(text(
            'SELECT version,snapshot FROM pm_weekly_plan_baselines WHERE plan_id=:id AND project_id=:p ORDER BY version DESC LIMIT 1'),
            {'id':plan_id,'p':project_id})).mappings().first()
        if not baseline:
            raise HTTPException(409, 'An approved baseline is required')
        commitments = json.loads(baseline['snapshot'])
        completed = 0
        for it in commitments:
            target = Decimal(it['weekly_target'])
            actual, evidence, undated = await self._actual_quantity(project_id,it['activity_id'],plan['start_date'],plan['end_date'])
            if undated or actual < 0:
                raise HTTPException(409, 'Resolve undated or negative execution evidence before closure')
            achievement = (actual / target if target else Decimal('0')).quantize(
                Decimal('.0001'), rounding=ROUND_HALF_EVEN)
            remaining = max(target - actual, Decimal('0'))
            total_target += target
            total_actual += actual
            met = target > 0 and actual >= target
            completed += int(met)
            results.append({'activity_id': it['activity_id'], 'target': str(target), 'actual': str(actual),
                            'achievement': str(achievement), 'remaining': str(remaining),
                            'commitment_met':met, 'evidence':evidence})
        ppc = (Decimal(completed) / len(commitments) * 100 if commitments else Decimal('0')).quantize(
            Decimal('.0001'), rounding=ROUND_HALF_EVEN)
        quantity_achievement = total_actual / total_target if total_target else Decimal(0)
        closure = json.dumps({'items': results, 'ppc': str(ppc), 'ppc_unit':'percent',
                              'quantity_achievement':str(quantity_achievement), 'baseline_version':baseline['version'], 'closed_at': now(),
                              'closed_by': self.request.state.user_id.hex}, sort_keys=True)
        await self.session.execute(text(
            'INSERT INTO pm_weekly_plan_closures(id,plan_id,project_id,snapshot) VALUES(:id,:plan,:p,:snapshot)'),
            {'id':uuid4().hex,'plan':plan_id,'p':project_id,'snapshot':closure})
        await self.session.execute(text(
            'UPDATE pm_weekly_plans SET status=:s, closure=:c, updated_at=:t WHERE id=:id'),
            {'s': 'closed', 'c': closure, 't': now(), 'id': plan_id})
        await self._log(plan_id, project_id, 'status:closed', note='closure computed')
        self.request.state.audit_details = {'entity_type': 'pm.weekly_plans', 'entity_id': str(UUID(plan_id)),
                                            'old': {'status': 'in_progress'},
                                            'new': {'status': 'closed', 'closure': closure},
                                            'summary': 'PM weekly plan closed'}
        return {'closure': json.loads(closure)}

    async def carryover(self, project_id, plan_id, payload):
        await self.project(project_id, 'pm.wep.manage')
        plan = await self._plan(plan_id, project_id)
        if plan['status'] != 'closed':
            raise HTTPException(409, 'Only a closed week can be carried over')
        if plan['carried_over']:
            raise HTTPException(409, 'This week was already carried over once')
        if payload.next_start_date.isoformat() <= plan['end_date']:
            raise HTTPException(409, 'Carryover must target a later, non-overlapping period')
        if await self.session.scalar(text('SELECT 1 FROM pm_weekly_plans WHERE project_id=:p AND week_code=:c'),
                                     {'p':project_id,'c':payload.next_week_code}):
            raise HTTPException(409, 'Week code already exists')
        closure = json.loads(plan['closure']) if plan['closure'] else {'items': []}
        new_id = uuid4().hex
        await self.session.execute(text(
            'INSERT INTO pm_weekly_plans (id,name,created_by,updated_at,project_id,week_code,start_date,end_date) '
            'VALUES (:id,:name,:by,:t,:p,:w,:s,:e)'),
            {'id': new_id, 'name': payload.next_week_code, 'by': self.request.state.user_id.hex, 't': now(),
             'p': project_id, 'w': payload.next_week_code, 's': payload.next_start_date.isoformat(),
             'e': payload.next_end_date.isoformat()})
        carried = 0
        for it in closure['items']:
            remaining = Decimal(it['remaining'])
            if remaining <= 0:
                continue
            carried += 1
            await self.session.execute(text(
                'INSERT INTO pm_weekly_plan_items (id,name,created_by,updated_at,project_id,plan_id,activity_id,weekly_target) '
                'VALUES (:id,:name,:by,:t,:p,:plan,:a,:target)'),
                {'id': uuid4().hex, 'name': it['activity_id'], 'by': self.request.state.user_id.hex, 't': now(),
                 'p': project_id, 'plan': new_id, 'a': it['activity_id'], 'target': str(remaining)})
        await self.session.execute(text(
            'UPDATE pm_weekly_plans SET carried_over=1, updated_at=:t WHERE id=:id'),
            {'t': now(), 'id': plan_id})
        await self._log(plan_id, project_id, 'carried_over', note=new_id)
        return {'next_plan_id': new_id, 'carried_items': carried}


