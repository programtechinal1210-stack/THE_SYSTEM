from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4
from fastapi import HTTPException
from sqlalchemy import text
from modules.module_pm.application.planning_service import PlanningService
from modules.module_pm.application.execution_service import ExecutionService

TRANSITIONS = {'planned': {'ready', 'blocked'}, 'ready': {'in_progress', 'blocked'},
               'in_progress': {'completed', 'blocked'}, 'blocked': {'ready', 'in_progress'},
               'completed': {'closed'}, 'closed': set()}

def now(): return datetime.now(timezone.utc).isoformat()

class DailyWorkService(PlanningService):
    async def _item(self, project_id, item_id):
        row = (await self.session.execute(text(
            'SELECT * FROM dw_daily_work_items WHERE id=:id AND project_id=:p AND deleted_at IS NULL'),
            {'id': item_id, 'p': project_id})).mappings().first()
        if not row: raise HTTPException(404, 'Daily work item unavailable')
        return dict(row)

    async def _readiness(self, row):
        checks = (await self.session.execute(text(
            'SELECT check_type,result,note,checked_at FROM dw_readiness_checks WHERE daily_work_id=:id ORDER BY checked_at'),
            {'id': row['id']})).mappings().all()
        blockers = (await self.session.execute(text(
            "SELECT id,blocker_type,description,status,created_at FROM dw_blockers WHERE daily_work_id=:id AND status='open' ORDER BY created_at"),
            {'id': row['id']})).mappings().all()
        latest_checks = {}
        for check in checks:
            latest_checks[check['check_type']] = check
        latest_results = list(latest_checks.values())
        status = 'not_ready' if blockers or any(c['result'] == 'blocked' for c in latest_results) else ('ready' if latest_results and all(c['result'] == 'ready' for c in latest_results) else 'warnings')
        return status, [dict(c) for c in checks], [dict(b) for b in blockers]

    async def present(self, row):
        status, checks, blockers = await self._readiness(row)
        result = dict(row)
        result['readiness_status'], result['readiness_checks'], result['blockers'] = status, checks, blockers
        result['actual_quantity'] = '0'
        result['actual_quantity_available'] = True
        result['remaining_quantity'] = str(max(Decimal(row['target_quantity']) - Decimal('0'), Decimal('0')))
        if row.get('source_type') == 'independent':
            actual = await self.session.scalar(text(
                "SELECT COALESCE(SUM(CAST(quantity_delta AS NUMERIC)),0) FROM dw_work_item_updates "
                "WHERE daily_work_id=:id AND source_type='independent' AND event_type='quantity'"
            ), {'id': row['id']})
            actual_decimal = Decimal(str(actual or '0'))
            result['actual_quantity'] = str(actual_decimal)
            result['remaining_quantity'] = str(max(Decimal(row['target_quantity']) - actual_decimal, Decimal('0')))
        elif row['work_order_id']:
            wo = await ExecutionService(self.session, self.request)._work_order(row['work_order_id'], row['project_id'])
            day_deltas = (await self.session.execute(text(
                "SELECT delta FROM pm_execution_quantity_events WHERE project_id=:p AND work_order_id=:wo "
                "AND substr(recorded_at,1,10)=:d ORDER BY recorded_at,id"
            ), {'p': row['project_id'], 'wo': row['work_order_id'], 'd': row['work_date']})).scalars().all()
            has_any_event = await self.session.scalar(text(
                'SELECT 1 FROM pm_execution_quantity_events WHERE project_id=:p AND work_order_id=:wo LIMIT 1'
            ), {'p': row['project_id'], 'wo': row['work_order_id']})
            cumulative = Decimal(str(wo['actual_quantity_snapshot']))
            result['work_order_actual_quantity'] = str(cumulative)
            result['actual_quantity_available'] = bool(has_any_event or cumulative == 0)
            if result['actual_quantity_available']:
                daily_actual = sum((Decimal(str(delta)) for delta in day_deltas), Decimal('0'))
                result['actual_quantity'] = str(daily_actual)
                result['remaining_quantity'] = str(max(Decimal(row['target_quantity']) - daily_actual, Decimal('0')))
            else:
                # Legacy totals without dated quantity events cannot be assigned to a work date.
                result['actual_quantity'] = None
                result['remaining_quantity'] = None
            result['work_order_status'] = wo['status']
        else:
            # A pm_activity/pm_work_order item without a linked work order has no
            # proven Actual source, and an independent stream does not apply.
            # Never substitute a fabricated zero or an assumed completion ratio.
            result['actual_quantity'] = None
            result['actual_quantity_available'] = False
            result['remaining_quantity'] = None
        return result

    async def list(self, project_id, work_date):
        await self.project(project_id, 'daily_work.view')
        rows = (await self.session.execute(text(
            'SELECT * FROM dw_daily_work_items WHERE project_id=:p AND work_date=:d AND deleted_at IS NULL ORDER BY created_at'),
            {'p': project_id, 'd': work_date})).mappings().all()
        return {'items': [await self.present(dict(r)) for r in rows]}

    async def create(self, project_id, payload):
        await self.project(project_id, 'daily_work.manage')
        aid = payload.activity_id.hex
        activity = (await self.session.execute(text(
            'SELECT * FROM pm_activities WHERE id=:a AND project_id=:p AND deleted_at IS NULL'), {'a': aid, 'p': project_id})).mappings().first()
        if not activity: raise HTTPException(422, 'Activity must belong to the project')
        if payload.work_order_id:
            wo = await ExecutionService(self.session, self.request)._work_order(payload.work_order_id.hex, project_id)
            if wo['activity_id'] != aid: raise HTTPException(422, 'Work order must match the activity')
        values = {'id': uuid4().hex, 'project_id': project_id, 'activity_id': aid,
                  'work_order_id': payload.work_order_id.hex if payload.work_order_id else None,
                  'work_date': payload.work_date.isoformat(), 'title': payload.title,
                  'target_quantity': str(payload.target_quantity), 'unit': payload.unit,
                  'assignee_user_id': payload.assignee_user_id.hex if payload.assignee_user_id else None,
                  'team_name': payload.team_name, 'shift': payload.shift, 'location': payload.location,
                  'notes': payload.notes, 'created_by': self.request.state.user_id.hex, 'updated_at': now()}
        try:
            await self.session.execute(text('INSERT INTO dw_daily_work_items ('+','.join(values)+') VALUES ('+','.join(':'+k for k in values)+')'), values)
        except Exception as exc:
            if 'UNIQUE' in str(exc): raise HTTPException(409, 'An item already exists for this activity and day') from None
            raise
        return await self.present(await self._item(project_id, values['id']))

    async def transition(self, project_id, item_id, target):
        await self.project(project_id, 'daily_work.review' if target == 'closed' else 'daily_work.manage')
        row = await self._item(project_id, item_id)
        if target not in TRANSITIONS.get(row['status'], set()): raise HTTPException(409, 'Invalid daily work transition')
        if target == 'in_progress' and row['readiness_status'] == 'not_ready': raise HTTPException(409, 'Daily work is not ready')
        await self.session.execute(text('UPDATE dw_daily_work_items SET status=:s,updated_at=:t WHERE id=:id'), {'s':target,'t':now(),'id':item_id})
        return await self.present(await self._item(project_id, item_id))

    async def check_readiness(self, project_id, item_id, payload):
        await self.project(project_id, 'daily_work.manage')
        row = await self._item(project_id, item_id)
        if payload.result not in ('ready', 'warning', 'blocked'):
            raise HTTPException(422, 'Invalid readiness result')
        await self.session.execute(text(
            'INSERT INTO dw_readiness_checks(id,daily_work_id,check_type,result,note,checked_by) VALUES(:id,:item,:kind,:result,:note,:by)'
        ), {'id': uuid4().hex, 'item': item_id, 'kind': payload.check_type, 'result': payload.result,
            'note': payload.note, 'by': self.request.state.user_id.hex})
        await self.session.execute(text(
            'UPDATE dw_daily_work_items SET readiness_status=:readiness,status=:status,updated_at=:t WHERE id=:id'
        ), {'readiness': 'not_ready' if payload.result == 'blocked' else ('ready' if payload.result == 'ready' else 'warnings'),
            'status': 'blocked' if payload.result == 'blocked' else ('ready' if payload.result == 'ready' and row['status'] == 'planned' else row['status']),
            't': now(), 'id': item_id})
        return await self.present(await self._item(project_id, item_id))

    async def record_progress(self, project_id, item_id, payload):
        await self.project(project_id, 'daily_work.manage')
        row = await self._item(project_id, item_id)
        if not row['work_order_id']: raise HTTPException(409, 'Actual progress requires a linked work order')
        wo = await ExecutionService(self.session, self.request)._work_order(row['work_order_id'], project_id)
        target = Decimal(wo['actual_quantity_snapshot']) + payload.quantity
        await ExecutionService(self.session, self.request).record_quantity(
            project_id, row['work_order_id'], target, payload.notes)
        if row['status'] in ('planned','ready'): await self.session.execute(text("UPDATE dw_daily_work_items SET status='in_progress',updated_at=:t WHERE id=:id"), {'t':now(),'id':item_id})
        return await self.present(await self._item(project_id, item_id))

    async def add_blocker(self, project_id, item_id, payload):
        await self.project(project_id, 'daily_work.manage'); await self._item(project_id, item_id)
        await self.session.execute(text('INSERT INTO dw_blockers(id,daily_work_id,blocker_type,description,created_by) VALUES(:id,:item,:kind,:description,:by)'), {'id':uuid4().hex,'item':item_id,'kind':payload.blocker_type,'description':payload.description,'by':self.request.state.user_id.hex})
        await self.session.execute(text("UPDATE dw_daily_work_items SET status='blocked',blocker_summary=:s,updated_at=:t WHERE id=:id"), {'s':payload.description,'t':now(),'id':item_id})
        return await self.present(await self._item(project_id, item_id))

    async def resolve_blocker(self, project_id, item_id, blocker_id, payload):
        await self.project(project_id, 'daily_work.manage'); await self._item(project_id, item_id)
        await self.session.execute(text("UPDATE dw_blockers SET status='resolved',resolved_note=:n,resolved_at=:t WHERE id=:b AND daily_work_id=:i"), {'n':payload.note,'t':now(),'b':blocker_id,'i':item_id})
        return await self.present(await self._item(project_id, item_id))
