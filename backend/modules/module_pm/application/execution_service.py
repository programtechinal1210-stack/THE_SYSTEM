"""Work orders, consumptions and quantity events share Core transactions, currency and audit."""
import json
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from .planning_service import PlanningService, now
from ..domain.execution import KINDS
from modules.module_currency.application.currency_service import CurrencyService

WO_TRANSITIONS = {
    'issued': {'in_progress'},
    'in_progress': set(),
    'completed': set(),
    'closed': set(),
    'rejected': set(),
}


class ExecutionService(PlanningService):
    def table(self, kind):
        return KINDS[kind][0]

    async def _row(self, kind, entity_id, project_id=None):
        where = 'id=:id' if project_id is None else 'id=:id AND project_id=:p'
        params = {'id': entity_id} if project_id is None else {'id': entity_id, 'p': project_id}
        r = (await self.session.execute(text(f'SELECT * FROM {self.table(kind)} WHERE {where}'), params)).mappings().first()
        return dict(r) if r else None

    async def _work_order(self, wo_id, project_id):
        row = await self._row('work_orders', wo_id, project_id)
        if not row or row['deleted_at']:
            raise HTTPException(404, 'Work order unavailable')
        return row

    async def _assert_project_open(self, project_id):
        if await self.session.scalar(text(
            "SELECT 1 FROM pm_completion_cases WHERE project_id=:p AND entity_type='project' AND status='closed'"),
            {'p': project_id}):
            raise HTTPException(409, 'لا يمكن تنفيذ أوامر جديدة بعد الإغلاق الرسمي للمشروع')

    async def _activity_plan(self, project_id, activity_id):
        row = (await self.session.execute(text(
            'SELECT planned_quantity FROM pm_activities WHERE id=:a AND project_id=:p AND deleted_at IS NULL'),
            {'a': activity_id, 'p': project_id})).mappings().first()
        if not row:
            raise HTTPException(409, 'Activity plan is unavailable for this work order')
        return Decimal(row['planned_quantity'])

    async def _other_activity_actual(self, project_id, activity_id, wo_id):
        value = await self.session.scalar(text(
            "SELECT COALESCE(SUM(CAST(actual_quantity_snapshot AS NUMERIC)),0) FROM pm_work_orders "
            "WHERE project_id=:p AND activity_id=:a AND id!=:wo AND deleted_at IS NULL AND status!='rejected'"),
            {'p': project_id, 'a': activity_id, 'wo': wo_id})
        return Decimal(str(value or '0'))

    async def list_work_orders(self, project_id, activity_id=None):
        await self.project(project_id, 'pm.execution.view')
        q = 'SELECT * FROM pm_work_orders WHERE project_id=:p AND deleted_at IS NULL'
        params = {'p': project_id}
        if activity_id:
            q += ' AND activity_id=:a'
            params['a'] = activity_id
        rows = (await self.session.execute(text(q + ' ORDER BY created_at'), params)).mappings()
        return {'items': [await self.present_wo(dict(r)) for r in rows]}

    async def detail_work_order(self, project_id, wo_id):
        await self.project(project_id, 'pm.execution.view')
        return await self.present_wo(await self._work_order(wo_id, project_id))

    async def _assert_work_order_issue_ready(self, project_id, activity_id):
        """Enforce the planning-to-execution gate at the command boundary."""
        project = await self.project(project_id, 'pm.execution.manage')
        await self._assert_project_open(project_id)
        if project['status'] != 'in_progress':
            raise HTTPException(
                409,
                'لا يمكن إصدار أمر تشغيل قبل اعتماد الخطة وبدء تنفيذ المشروع',
            )

        activity = (await self.session.execute(text(
            'SELECT approval_status FROM pm_activities '
            'WHERE id=:activity_id AND project_id=:project_id AND deleted_at IS NULL'),
            {'activity_id': activity_id, 'project_id': project_id})).mappings().first()
        if not activity:
            raise HTTPException(422, 'Activity must belong to this project and be active')
        if activity['approval_status'] != 'approved':
            raise HTTPException(
                409,
                'لا يمكن إصدار أمر تشغيل قبل إقرار النشاط ضمن الخطة المعتمدة',
            )

        active_order = await self.session.scalar(text(
            "SELECT 1 FROM pm_work_orders "
            "WHERE project_id=:project_id AND activity_id=:activity_id "
            "AND deleted_at IS NULL AND status IN ('issued','in_progress') LIMIT 1"),
            {'project_id': project_id, 'activity_id': activity_id})
        if active_order:
            raise HTTPException(409, 'لا يمكن إصدار أمر آخر لنشاط لديه أمر تشغيل نشط')
        partial_close = await self.session.scalar(text(
            "SELECT 1 FROM pm_work_orders WHERE project_id=:project_id AND activity_id=:activity_id "
            "AND deleted_at IS NULL AND partial_close_reason!='' LIMIT 1"),
            {'project_id': project_id, 'activity_id': activity_id})
        if partial_close:
            raise HTTPException(409, 'أُغلق النشاط جزئيًا؛ لا يمكن إصدار أمر تشغيل إضافي له')
        return project

    async def _next_work_order_code(self, project_id, project_code):
        token = re.sub(r'[^A-Za-z0-9_-]+', '-', str(project_code or 'PROJECT')).strip('-') or 'PROJECT'
        prefix = f'WO-{token}-'
        values = await self.session.execute(text(
            'SELECT work_order_code FROM pm_work_orders WHERE project_id=:project_id'),
            {'project_id': project_id},
        )
        codes = [str(value or '') for value in values.scalars()]
        existing = {code.casefold() for code in codes}
        sequence = 1
        for code in codes:
            if code.casefold().startswith(prefix.casefold()):
                suffix = code[len(prefix):]
                if suffix.isdigit():
                    sequence = max(sequence, int(suffix) + 1)
        candidate = f'{prefix}{sequence:03d}'
        while candidate.casefold() in existing:
            sequence += 1
            candidate = f'{prefix}{sequence:03d}'
        return candidate

    async def _next_consumption_code(self, project_id, work_order_id, work_order_code):
        token = re.sub(r'[^A-Za-z0-9_-]+', '-', str(work_order_code or 'WORK-ORDER')).strip('-') or 'WORK-ORDER'
        prefix = f'CON-{token}-'
        values = await self.session.execute(text(
            'SELECT consumption_code FROM pm_work_order_consumptions '
            'WHERE project_id=:project_id AND work_order_id=:work_order_id'),
            {'project_id': project_id, 'work_order_id': work_order_id},
        )
        codes = [str(value or '') for value in values.scalars()]
        existing = {code.casefold() for code in codes}
        sequence = 1
        for code in codes:
            if code.casefold().startswith(prefix.casefold()):
                suffix = code[len(prefix):]
                if suffix.isdigit():
                    sequence = max(sequence, int(suffix) + 1)
        candidate = f'CON-{token}-{sequence:03d}'
        while candidate.casefold() in existing:
            sequence += 1
            candidate = f'CON-{token}-{sequence:03d}'
        return candidate

    async def create_work_order(self, project_id, payload):
        project = await self._assert_work_order_issue_ready(project_id, payload.activity_id.hex)
        act = await self.repo.get('activities', payload.activity_id.hex)
        if not act or act['project_id'] != project_id or act['deleted_at']:
            raise HTTPException(422, 'Activity must belong to this project and be active')
        values = payload.model_dump(mode='json')
        values['activity_id'] = UUID(values['activity_id']).hex
        values['assignee_user_id'] = UUID(values['assignee_user_id']).hex if values.get('assignee_user_id') else None
        # Ignore any client-provided code: this value is generated from the
        # persisted project work orders and is authoritative only on the server.
        values['work_order_code'] = await self._next_work_order_code(project_id, project['project_code'])
        values['name'] = values['work_order_code']
        values['project_id'] = project_id
        values['created_by'] = self.request.state.user_id.hex
        values['id'] = uuid4().hex
        values['updated_at'] = now()
        try:
            await self.session.execute(text(
                f'INSERT INTO pm_work_orders ({",".join(values)}) VALUES ({",".join(":" + k for k in values)})'), values)
        except IntegrityError:
            raise HTTPException(409, 'Work order code already exists') from None
        return await self.present_wo(await self._row('work_orders', values['id']))

    async def present_wo(self, row):
        result = dict(row)
        result['actual_cost'] = await self.actual_cost(row['id'])
        return result

    async def transition(self, project_id, wo_id, target):
        project = await self.project(project_id, 'pm.execution.manage')
        await self._assert_project_open(project_id)
        row = await self._work_order(wo_id, project_id)
        if target not in WO_TRANSITIONS.get(row['status'], set()):
            raise HTTPException(409, 'Invalid work order transition')
        updates = {'status': target, 'updated_at': now()}
        if target == 'in_progress' and not row['start_date']:
            updates['start_date'] = now()
        await self.session.execute(text(
            'UPDATE pm_work_orders SET ' + ','.join(f'{k}=:{k}' for k in updates) + ' WHERE id=:id'),
            dict(updates, id=wo_id))
        self.request.state.audit_details = {'entity_type': 'pm.work_orders', 'entity_id': str(UUID(wo_id)),
                                            'old': {'status': row['status']}, 'new': {'status': target},
                                            'summary': 'PM work order status change'}
        return await self.present_wo(await self._row('work_orders', wo_id))

    async def update_work_order(self, project_id, wo_id, payload):
        project = await self.project(project_id, 'pm.execution.manage')
        await self._assert_project_open(project_id)
        row = await self._work_order(wo_id, project_id)
        if row['status'] != 'issued' or Decimal(row['actual_quantity_snapshot']) != 0:
            raise HTTPException(409, 'لا يمكن تعديل الأمر بعد بدء التنفيذ')
        has_events = await self.session.scalar(text(
            'SELECT 1 FROM pm_execution_quantity_events WHERE work_order_id=:wo LIMIT 1'), {'wo': wo_id})
        has_consumptions = await self.session.scalar(text(
            'SELECT 1 FROM pm_work_order_consumptions WHERE work_order_id=:wo AND deleted_at IS NULL LIMIT 1'),
            {'wo': wo_id})
        if row.get('approved_by') or has_events or has_consumptions:
            raise HTTPException(409, 'لا يمكن تعديل أمر بدأ تنفيذه أو اتُخذ قرار بشأنه')
        values = payload.model_dump(mode='json')
        # Never trust a client-provided business key. The form may show a
        # preview, but the persisted code is assigned here from current data.
        values['work_order_code'] = await self._next_work_order_code(project_id, project['project_code'])
        assignee = values.get('assignee_user_id')
        if assignee:
            project = await self.repo.get('projects', project_id)
            active_user = await self.session.scalar(text(
                'SELECT 1 FROM users WHERE id=:id AND is_active=1 AND organization_id=:org'),
                {'id': UUID(assignee).hex, 'org': project['organization_id']})
            if not active_user:
                raise HTTPException(422, 'المكلّف غير متاح ضمن الجهة التنظيمية للمشروع')
            values['assignee_user_id'] = UUID(assignee).hex
        values['issue_date'] = values.get('issue_date') or row.get('issue_date')
        values['updated_at'] = now()
        await self.session.execute(text(
            'UPDATE pm_work_orders SET assignee_user_id=:assignee_user_id,issue_date=:issue_date,'
            'planned_start_date=:planned_start_date,notes=:notes,updated_at=:updated_at '
            'WHERE id=:id AND project_id=:p'),
            dict(values, id=wo_id, p=project_id))
        self.request.state.audit_details = {
            'entity_type': 'pm.work_orders', 'entity_id': str(UUID(wo_id)),
            'old': {'assignee_user_id': row.get('assignee_user_id'), 'issue_date': row.get('issue_date'),
                    'planned_start_date': row.get('planned_start_date'), 'notes': row.get('notes')},
            'new': values, 'summary': 'PM work order updated before execution'}
        return await self.present_wo(await self._work_order(wo_id, project_id))

    async def approve(self, project_id, wo_id):
        await self.project(project_id, 'pm.execution.manage')
        await self._assert_project_open(project_id)
        row = await self._work_order(wo_id, project_id)
        if row['status'] not in ('in_progress', 'closed') or row.get('approved_by'):
            raise HTTPException(409, 'الأمر غير متاح للاعتماد في حالته الحالية')
        quantity = Decimal(row['actual_quantity_snapshot'])
        if quantity <= 0:
            raise HTTPException(409, 'لا يمكن اعتماد أمر بلا إنجاز مسجل')
        planned = await self._activity_plan(project_id, row['activity_id'])
        is_partial = bool(row.get('partial_close_reason'))
        if is_partial:
            if row['status'] != 'closed' or quantity >= planned:
                raise HTTPException(409, 'حالة الإغلاق الجزئي غير متسقة مع الكمية المسجلة')
            target = 'closed'
        else:
            if quantity < planned:
                raise HTTPException(409, 'يتطلب الاعتماد اكتمال الكمية المخططة أو إغلاقًا جزئيًا موثقًا')
            target = 'completed'
        actor = self.request.state.user_id.hex
        stamp = now()
        await self.session.execute(text(
            'UPDATE pm_work_orders SET approved_by=:actor,approved_at=:at,status=:status,'
            'completion_date=COALESCE(completion_date,:at),updated_at=:at WHERE id=:id AND project_id=:p'),
            {'actor': actor, 'at': stamp, 'status': target, 'id': wo_id, 'p': project_id})
        self.request.state.audit_details = {
            'entity_type': 'pm.work_orders', 'entity_id': str(UUID(wo_id)),
            'old': {'status': row['status'], 'approved_by': row.get('approved_by')},
            'new': {'status': target, 'approved_by': actor, 'approved_at': stamp,
                    'actual_quantity': str(quantity), 'partial': is_partial},
            'summary': 'PM work order approved'}
        return await self.present_wo(await self._work_order(wo_id, project_id))

    async def reject(self, project_id, wo_id, reason):
        await self.project(project_id, 'pm.execution.manage')
        await self._assert_project_open(project_id)
        row = await self._work_order(wo_id, project_id)
        if row['status'] not in ('issued', 'in_progress'):
            raise HTTPException(409, 'لا يمكن رفض أمر بعد إغلاقه أو اتخاذ قرار بشأنه')
        actor = self.request.state.user_id.hex
        stamp = now()
        await self.session.execute(text(
            "UPDATE pm_work_orders SET status='rejected',rejected_by=:actor,rejected_at=:at,"
            'rejection_reason=:reason,updated_at=:at WHERE id=:id AND project_id=:p'),
            {'actor': actor, 'at': stamp, 'reason': reason.strip(), 'id': wo_id, 'p': project_id})
        self.request.state.audit_details = {
            'entity_type': 'pm.work_orders', 'entity_id': str(UUID(wo_id)),
            'old': {'status': row['status']},
            'new': {'status': 'rejected', 'reason': reason.strip(), 'rejected_by': actor, 'rejected_at': stamp},
            'summary': 'PM work order rejected'}
        return await self.present_wo(await self._work_order(wo_id, project_id))

    async def close_partially(self, project_id, wo_id, reason):
        await self.project(project_id, 'pm.execution.manage')
        await self._assert_project_open(project_id)
        row = await self._work_order(wo_id, project_id)
        if row['status'] not in ('issued', 'in_progress'):
            raise HTTPException(409, 'لا يمكن إغلاق الأمر جزئيًا في حالته الحالية')
        quantity = Decimal(row['actual_quantity_snapshot'])
        planned = await self._activity_plan(project_id, row['activity_id'])
        if quantity <= 0 or quantity >= planned:
            raise HTTPException(409, 'الإغلاق الجزئي يتطلب إنجازًا أكبر من صفر وأقل من الكمية المخططة')
        actor = self.request.state.user_id.hex
        stamp = now()
        await self.session.execute(text(
            "UPDATE pm_work_orders SET status='closed',partial_close_reason=:reason,partial_closed_by=:actor,"
            'partial_closed_at=:at,closure_date=:at,completion_date=COALESCE(completion_date,:at),updated_at=:at '
            'WHERE id=:id AND project_id=:p'),
            {'reason': reason.strip(), 'actor': actor, 'at': stamp, 'id': wo_id, 'p': project_id})
        self.request.state.audit_details = {
            'entity_type': 'pm.work_orders', 'entity_id': str(UUID(wo_id)),
            'old': {'status': row['status'], 'actual_quantity': str(quantity)},
            'new': {'status': 'closed', 'partial_close_reason': reason.strip(),
                    'partial_closed_by': actor, 'partial_closed_at': stamp},
            'summary': 'PM work order partially closed'}
        return await self.present_wo(await self._work_order(wo_id, project_id))

    async def record_quantity(self, project_id, wo_id, quantity, notes=''):
        await self.project(project_id, 'pm.execution.manage')
        await self._assert_project_open(project_id)
        row = await self._work_order(wo_id, project_id)
        if row['status'] in ('completed', 'closed', 'rejected'):
            raise HTTPException(409, 'Quantity can only be recorded before closure')
        before = Decimal(row['actual_quantity_snapshot'])
        after = Decimal(str(quantity))
        planned = await self._activity_plan(project_id, row['activity_id'])
        if after < before:
            raise HTTPException(409, 'Cumulative execution quantity cannot decrease')
        if after == before:
            raise HTTPException(409, 'Cumulative execution quantity has no new progress')
        if after > planned:
            raise HTTPException(409, 'لا يمكن أن تتجاوز الكمية المنفذة الكمية المخططة')
        activity_actual = await self._other_activity_actual(project_id, row['activity_id'], wo_id) + after
        if activity_actual > planned:
            raise HTTPException(409, 'إجمالي إنجاز النشاط عبر أوامر التشغيل سيتجاوز الكمية المخططة')
        delta = after - before
        event_id = uuid4().hex
        await self.session.execute(text(
            'INSERT INTO pm_execution_quantity_events '
            '(id, project_id, work_order_id, activity_id, before_quantity, after_quantity, delta, recorded_by, recorded_at, notes) '
            'VALUES (:id, :p, :wo, :act, :before, :after, :delta, :by, :at, :notes)'),
            {'id': event_id, 'p': project_id, 'wo': wo_id, 'act': row['activity_id'],
             'before': str(before), 'after': str(after), 'delta': str(delta),
             'by': self.request.state.user_id.hex, 'at':now(), 'notes': notes})
        stamp = now()
        await self.session.execute(text(
            "UPDATE pm_work_orders SET actual_quantity_snapshot=:q,status='in_progress', "
            'start_date=COALESCE(start_date,:t),updated_at=:t WHERE id=:id'),
            {'q': str(after), 't': stamp, 'id': wo_id})
        self.request.state.audit_details = {
            'entity_type': 'pm.work_orders', 'entity_id': str(UUID(wo_id)),
            'old': {'actual_quantity': str(before), 'status': row['status']},
            'new': {'actual_quantity': str(after), 'delta': str(delta), 'status': 'in_progress'},
            'summary': 'PM work order progress recorded'}
        return {'event_id': event_id, 'before': str(before), 'after': str(after), 'delta': str(delta)}

    async def quantity_events(self, project_id, wo_id):
        await self.project(project_id, 'pm.execution.view')
        await self._work_order(wo_id, project_id)
        rows = (await self.session.execute(text(
            'SELECT * FROM pm_execution_quantity_events WHERE work_order_id=:wo AND project_id=:p ORDER BY recorded_at,id'),
            {'wo': wo_id, 'p': project_id})).mappings()
        return {'items': [dict(r) for r in rows]}

    # ---- Consumptions ----
    async def preview_consumption_cost(self, project_id, source, rate_date,
                                       quantity=None, unit_price=None):
        """Quote an actual-cost conversion using the same YER-anchored contract as planning."""
        project = await self.project(project_id, 'pm.execution.manage')
        try:
            rate_date = date.fromisoformat(str(rate_date)).isoformat()
        except ValueError:
            raise HTTPException(422, 'تاريخ المصارفة غير صالح') from None
        result = await CurrencyService(self.session).get_anchor_snapshot(
            source, project['currency'], rate_date, 'YER')
        result['rate'] = str(result['rate']) if result['rate'] is not None else None
        result['cost_currency'] = project['currency']
        result['source_amount'] = None
        result['actual_cost'] = None
        if result['available'] and quantity not in (None, '') and unit_price not in (None, ''):
            try:
                source_amount = Decimal(str(quantity)) * Decimal(str(unit_price))
                if source_amount < 0:
                    raise ValueError
            except (InvalidOperation, ValueError):
                raise HTTPException(422, 'الكمية وسعر الوحدة يجب أن يكونا مبالغ صالحة') from None
            result['source_amount'] = str(source_amount)
            result['actual_cost'] = str(source_amount * Decimal(result['rate']))
        return result

    async def list_consumptions(self, project_id, work_order_id):
        await self.project(project_id, 'pm.execution.view')
        await self._work_order(work_order_id, project_id)
        rows = (await self.session.execute(text(
            'SELECT * FROM pm_work_order_consumptions WHERE work_order_id=:wo AND project_id=:p AND deleted_at IS NULL ORDER BY created_at,id'),
            {'wo': work_order_id, 'p': project_id})).mappings()
        return {'items': [await self.present_consumption(dict(r)) for r in rows]}

    async def create_consumption(self, project_id, payload):
        await self.project(project_id, 'pm.execution.manage')
        await self._assert_project_open(project_id)
        wo = await self._work_order(payload.work_order_id.hex, project_id)
        if wo['status'] in ('completed', 'rejected') or (
            wo['status'] == 'closed' and (not wo.get('partial_close_reason') or wo.get('approved_by'))
        ):
            raise HTTPException(409, 'لا يمكن تسجيل استهلاك على أمر مكتمل أو مرفوض أو مغلق نهائيًا')
        project = await self.repo.get('projects', project_id)
        values = payload.model_dump(mode='json')
        values['work_order_id'] = UUID(values['work_order_id']).hex
        # The displayed value is only a preview; the server owns the business key.
        values['consumption_code'] = await self._next_consumption_code(
            project_id, values['work_order_id'], wo['work_order_code'])
        values['name'] = values['consumption_code']
        values['project_id'] = project_id
        values['exchange_rate_snapshot'] = await self.snapshot(
            payload.currency, project['currency'], payload.rate_date.isoformat(), anchor='YER')
        values['created_by'] = self.request.state.user_id.hex
        values['id'] = uuid4().hex
        values['updated_at'] = now()
        try:
            await self.session.execute(text(
                f'INSERT INTO pm_work_order_consumptions ({",".join(values)}) VALUES ({",".join(":" + k for k in values)})'), values)
        except IntegrityError:
            raise HTTPException(409, 'Consumption code already exists') from None
        consumption = await self.present_consumption(await self._row('consumptions', values['id']))
        self.request.state.audit_details = {
            'entity_type': 'pm.work_order_consumptions', 'entity_id': str(UUID(values['id'])),
            'new': {'work_order_id': str(UUID(values['work_order_id'])),
                    'item_name': payload.item_name, 'quantity': str(payload.quantity),
                    'cost': consumption['cost']},
            'summary': 'PM work order consumption recorded'}
        return consumption

    async def present_consumption(self, row):
        result = dict(row)
        snap = json.loads(row['exchange_rate_snapshot'])
        result['cost'] = str(Decimal(row['quantity']) * Decimal(row['unit_price']) * Decimal(snap['rate']))
        result['exchange_rate_snapshot'] = snap
        return result

    async def actual_cost(self, work_order_id):
        rows = (await self.session.execute(text(
            'SELECT quantity, unit_price, exchange_rate_snapshot FROM pm_work_order_consumptions '
            'WHERE work_order_id=:wo AND deleted_at IS NULL'),
            {'wo': work_order_id})).mappings()
        total = Decimal('0')
        for r in rows:
            snap = json.loads(r['exchange_rate_snapshot'])
            total += Decimal(r['quantity']) * Decimal(r['unit_price']) * Decimal(snap['rate'])
        return str(total)

