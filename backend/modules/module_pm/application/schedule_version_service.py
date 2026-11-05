import hashlib
import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from .actual_read_adapter import ActualReadAdapter
from .planning_service import PlanningService
from ..domain.forecast_recalculation import remaining_work_minutes
from ..domain.scheduling_calendar import CalendarException, WorkCalendar
from ..domain.scheduling_engine import (
    ActivityDependency, ActivityScheduleInput, SchedulingValidationError, calculate_schedule,
)


def now():
    return datetime.now(timezone.utc).isoformat()


class ScheduleVersionService(PlanningService):
    @staticmethod
    def _decision_context(row):
        """Bounded audit context; it contains references and hashes, never credentials."""
        return {key: row.get(key) for key in (
            'baseline_id', 'version_no', 'status', 'actual_as_of', 'actual_input_hash',
            'actual_output_hash', 'actual_source_event_ids_json', 'calculation_inputs_hash',
            'reviewed_against_version_id')}

    async def _current_actual_forecast_hash(self, project_id, forecast, project):
        """Rebuild the immutable S-04.3 input fingerprint without writing a Forecast."""
        if not forecast.get('actual_as_of'):
            return None, None
        baseline = (await self.session.execute(text(
            'SELECT id FROM pm_plan_baselines WHERE id=:b AND project_id=:p'),
            {'b': forecast['baseline_id'], 'p': project_id})).mappings().first()
        if not baseline:
            raise HTTPException(409, 'Forecast baseline is no longer available; recalculate before approval')
        actual = await ActualReadAdapter(self.session, self.request).read(
            project_id, datetime.fromisoformat(forecast['actual_as_of']))
        blockers = [issue for issue in actual['issues'] if issue['blocking']]
        if blockers:
            raise HTTPException(409, {'detail': 'Actual input is no longer forecastable; recalculate before approval',
                                      'issues': blockers})
        calendar_id = project.get('default_schedule_calendar_id')
        calendar = None
        if calendar_id:
            calendar = (await self.session.execute(text(
                'SELECT timezone,weekly_pattern_json FROM pm_schedule_calendars '
                'WHERE id=:id AND is_active=1 AND deleted_at IS NULL'),
                {'id': calendar_id})).mappings().first()
        if not calendar:
            raise HTTPException(409, 'Project schedule calendar changed or is unavailable; recalculate before approval')
        exceptions = (await self.session.execute(text(
            "SELECT id,starts_at,ends_at,availability_mode,reason FROM pm_schedule_calendar_exceptions "
            "WHERE calendar_id=:id AND deleted_at IS NULL ORDER BY starts_at,id"),
            {'id': calendar_id})).mappings().all()
        baseline_items = (await self.session.execute(text(
            "SELECT entity_id,snapshot FROM pm_plan_baseline_items "
            "WHERE baseline_id=:b AND entity_kind='activities' ORDER BY entity_id"),
            {'b': baseline['id']})).mappings().all()
        dependencies = (await self.session.execute(text(
            'SELECT predecessor_id,successor_id,dependency_type FROM pm_activity_dependencies '
            'WHERE project_id=:p ORDER BY predecessor_id,successor_id,dependency_type'),
            {'p': project_id})).mappings().all()
        source = {
            'contract_version': 's04.3-v1', 'baseline_id': baseline['id'],
            'actual_input_hash': actual['input_hash'], 'actual_output_hash': actual['output_hash'],
            'actual_as_of': actual['actual_as_of'],
            'calendar': {'id': calendar_id, 'timezone': calendar['timezone'],
                         'weekly_pattern_json': calendar['weekly_pattern_json'],
                         'exceptions': [dict(row) for row in exceptions]},
            'baseline_items': [dict(row) for row in baseline_items],
            'dependencies': [dict(row) for row in dependencies],
        }
        digest = hashlib.sha256(json.dumps(source, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        return digest, actual

    async def recalculate_actual(self, project_id, payload):
        """Create one idempotent draft from the immutable Actual read contract."""
        project = await self.project(project_id, 'pm.schedule.manage')
        baseline = (await self.session.execute(text(
            'SELECT id,start_date FROM pm_plan_baselines WHERE id=:b AND project_id=:p'),
            {'b': payload.baseline_id.hex, 'p': project_id})).mappings().first()
        if not baseline:
            raise HTTPException(422, 'Baseline must belong to this project')
        actual = await ActualReadAdapter(self.session, self.request).read(project_id, payload.actual_as_of)
        blockers = [issue for issue in actual['issues'] if issue['blocking']]
        if blockers:
            raise HTTPException(422, {'detail': 'Actual input is not forecastable', 'issues': blockers})
        existing = (await self.session.execute(text(
            "SELECT id,version_no,status,calculation_inputs_hash FROM pm_schedule_versions "
            "WHERE project_id=:p AND baseline_id=:b AND actual_input_hash=:h AND status='draft'"),
            {'p': project_id, 'b': baseline['id'], 'h': actual['input_hash']})).mappings().first()
        if existing:
            return dict(existing, idempotent=True)

        calendar_id = project.get('default_schedule_calendar_id')
        calendar_row = None
        if calendar_id:
            calendar_row = (await self.session.execute(text(
                'SELECT timezone,weekly_pattern_json FROM pm_schedule_calendars '
                'WHERE id=:id AND is_active=1 AND deleted_at IS NULL'),
                {'id': calendar_id})).mappings().first()
        if not calendar_row:
            raise HTTPException(409, 'Project has no explicit active schedule calendar')
        calendar = WorkCalendar(calendar_row['timezone'], json.loads(calendar_row['weekly_pattern_json']))
        exception_rows = (await self.session.execute(text(
            "SELECT id,starts_at,ends_at,availability_mode,reason FROM pm_schedule_calendar_exceptions "
            "WHERE calendar_id=:id AND deleted_at IS NULL ORDER BY starts_at,id"),
            {'id': calendar_id})).mappings().all()
        exceptions = tuple(CalendarException(
            start=datetime.fromisoformat(row['starts_at']), end=datetime.fromisoformat(row['ends_at']),
            availability_mode=row['availability_mode']) for row in exception_rows)
        baseline_rows = (await self.session.execute(text(
            "SELECT entity_id,snapshot FROM pm_plan_baseline_items "
            "WHERE baseline_id=:b AND entity_kind='activities' ORDER BY entity_id"),
            {'b': baseline['id']})).mappings().all()
        if not baseline_rows:
            raise HTTPException(409, 'Baseline has no activities')
        actual_by_activity = {item['activity_id']: item for item in actual['items']}
        activities, minutes, quantities = [], {}, {}
        for row in baseline_rows:
            snapshot = json.loads(row['snapshot'])
            item = actual_by_activity.get(row['entity_id'])
            if not item:
                raise HTTPException(409, 'Baseline activity is unavailable in Actual input')
            planned_minutes = int(float(snapshot.get('planned_duration') or 0) * 60) or None
            work = remaining_work_minutes(item['planned_quantity'], item['remaining_quantity'], planned_minutes)
            minutes[row['entity_id']], quantities[row['entity_id']] = work, item
            activities.append(ActivityScheduleInput(row['entity_id'], calendar, work, exceptions=exceptions))
        dependencies = (await self.session.execute(text(
            'SELECT predecessor_id,successor_id,dependency_type FROM pm_activity_dependencies '
            'WHERE project_id=:p ORDER BY predecessor_id,successor_id,dependency_type'),
            {'p': project_id})).mappings().all()
        try:
            calculation = calculate_schedule(
                max(datetime.fromisoformat(baseline['start_date']).replace(tzinfo=timezone.utc),
                    datetime.fromisoformat(actual['actual_as_of'])),
                activities, [ActivityDependency(**dict(dependency)) for dependency in dependencies])
        except (SchedulingValidationError, ValueError) as exc:
            raise HTTPException(422, f'Cannot calculate forecast: {exc}') from None
        source = {
            'contract_version': 's04.3-v1', 'baseline_id': baseline['id'],
            'actual_input_hash': actual['input_hash'], 'actual_output_hash': actual['output_hash'],
            'actual_as_of': actual['actual_as_of'],
            'calendar': {'id': calendar_id, 'timezone': calendar_row['timezone'],
                         'weekly_pattern_json': calendar_row['weekly_pattern_json'],
                         'exceptions': [dict(row) for row in exception_rows]},
            'baseline_items': [dict(row) for row in baseline_rows],
            'dependencies': [dict(row) for row in dependencies],
        }
        digest = hashlib.sha256(json.dumps(source, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        event_ids = sorted({event_id for item in actual['items'] for event_id in item['source_event_ids']})
        number = await self.session.scalar(text(
            'SELECT COALESCE(MAX(version_no),0)+1 FROM pm_schedule_versions WHERE project_id=:p'), {'p': project_id})
        version_id = uuid4().hex
        try:
            await self.session.execute(text(
                'INSERT INTO pm_schedule_versions('
                'id,project_id,baseline_id,version_no,calculation_inputs_hash,reason,created_by,'
                'actual_as_of,actual_input_hash,actual_output_hash,actual_source_event_ids_json) '
                'VALUES(:id,:p,:b,:n,:h,:r,:u,:as_of,:aih,:aoh,:events)'),
                {'id': version_id, 'p': project_id, 'b': baseline['id'], 'n': number, 'h': digest,
                 'r': payload.reason, 'u': self.request.state.user_id.hex, 'as_of': actual['actual_as_of'],
                 'aih': actual['input_hash'], 'aoh': actual['output_hash'], 'events': json.dumps(event_ids)})
        except IntegrityError:
            await self.session.rollback()
            existing = (await self.session.execute(text(
                "SELECT id,version_no,status,calculation_inputs_hash FROM pm_schedule_versions "
                "WHERE project_id=:p AND baseline_id=:b AND actual_input_hash=:h AND status='draft'"),
                {'p': project_id, 'b': baseline['id'], 'h': actual['input_hash']})).mappings().first()
            if existing:
                return dict(existing, idempotent=True)
            raise
        for item in calculation.items:
            quantity = quantities[item.activity_id]
            await self.session.execute(text(
                'INSERT INTO pm_schedule_items('
                'id,schedule_version_id,project_id,activity_id,scheduling_state,block_reason,'
                'remaining_work_minutes,early_start,early_finish,late_start,late_finish,total_float_minutes,is_critical,'
                'planned_quantity,actual_quantity_at_measurement,remaining_quantity) '
                'VALUES(:id,:v,:p,:a,:s,:r,:m,:es,:ef,:ls,:lf,:f,:c,:pq,:aq,:rq)'),
                {'id': uuid4().hex, 'v': version_id, 'p': project_id, 'a': item.activity_id,
                 's': item.scheduling_state, 'r': item.block_reason, 'm': minutes[item.activity_id],
                 'es': item.early_start.isoformat() if item.early_start else None,
                 'ef': item.early_finish.isoformat() if item.early_finish else None,
                 'ls': item.late_start.isoformat() if item.late_start else None,
                 'lf': item.late_finish.isoformat() if item.late_finish else None,
                 'f': item.total_float_minutes, 'c': int(item.is_critical),
                 'pq': quantity['planned_quantity'], 'aq': quantity['actual_quantity'],
                 'rq': quantity['remaining_quantity']})
        self.request.state.audit_details = {
            'entity_type': 'pm.schedule_versions', 'entity_id': str(UUID(version_id)), 'old': None,
            'new': {'status': 'draft', 'baseline_id': baseline['id'], 'version_no': number,
                    'calculation_inputs_hash': digest, 'actual_as_of': actual['actual_as_of'],
                    'actual_input_hash': actual['input_hash'], 'actual_output_hash': actual['output_hash'],
                    'source_event_ids': event_ids, 'calculation_state': calculation.state},
            'summary': 'PM Actual-based forecast draft created'}
        return {'id': version_id, 'version_no': number, 'status': 'draft',
                'calculation_state': calculation.state, 'calculation_inputs_hash': digest,
                'idempotent': False}

    async def _version(self, project_id, version_id, permission='pm.schedule.view'):
        await self.project(project_id, permission)
        row = (await self.session.execute(text(
            'SELECT * FROM pm_schedule_versions WHERE id=:id AND project_id=:p'),
            {'id': version_id, 'p': project_id})).mappings().first()
        if not row:
            raise HTTPException(404, 'Schedule version not found')
        return dict(row)

    async def list(self, project_id):
        await self.project(project_id, 'pm.schedule.view')
        rows = (await self.session.execute(text(
            'SELECT id,baseline_id,version_no,status,reason,actual_as_of,effective_from,created_at,proposed_at,'
            'approved_by,approved_at,approval_reason,rejected_by,rejected_at,rejection_reason '
            'FROM pm_schedule_versions WHERE project_id=:p ORDER BY version_no DESC'),
            {'p': project_id})).mappings()
        return {'items': [dict(row) for row in rows]}

    async def create(self, project_id, payload):
        project = await self.project(project_id, 'pm.schedule.manage')
        baseline = (await self.session.execute(text(
            'SELECT id,start_date FROM pm_plan_baselines WHERE id=:b AND project_id=:p'),
            {'b': payload.baseline_id.hex, 'p': project_id})).mappings().first()
        if not baseline:
            raise HTTPException(422, 'Baseline must belong to this project')
        calendar_id = project.get('default_schedule_calendar_id')
        calendar_row = None
        if calendar_id:
            calendar_row = (await self.session.execute(text(
                'SELECT timezone,weekly_pattern_json FROM pm_schedule_calendars '
                'WHERE id=:id AND is_active=1 AND deleted_at IS NULL'),
                {'id': calendar_id})).mappings().first()
        if not calendar_row:
            raise HTTPException(409, 'Project has no explicit active schedule calendar')
        calendar = WorkCalendar(calendar_row['timezone'], json.loads(calendar_row['weekly_pattern_json']))
        exception_rows = (await self.session.execute(text(
            "SELECT id,starts_at,ends_at,availability_mode,reason FROM pm_schedule_calendar_exceptions "
            "WHERE calendar_id=:id AND deleted_at IS NULL ORDER BY starts_at,id"),
            {'id': calendar_id})).mappings().all()
        exceptions = tuple(CalendarException(
            start=datetime.fromisoformat(row['starts_at']),
            end=datetime.fromisoformat(row['ends_at']),
            availability_mode=row['availability_mode'],
        ) for row in exception_rows)
        rows = (await self.session.execute(text(
            "SELECT entity_id,snapshot FROM pm_plan_baseline_items "
            "WHERE baseline_id=:b AND entity_kind='activities' ORDER BY entity_id"),
            {'b': baseline['id']})).mappings().all()
        if not rows:
            raise HTTPException(409, 'Baseline has no activities')

        activities, work_minutes = [], {}
        for row in rows:
            duration = json.loads(row['snapshot']).get('planned_duration')
            minutes = int(float(duration or 0) * 60) if duration else None
            if minutes is not None and minutes <= 0:
                minutes = None
            work_minutes[row['entity_id']] = minutes
            activities.append(ActivityScheduleInput(
                row['entity_id'], calendar, minutes, exceptions=exceptions))
        dependencies = (await self.session.execute(text(
            'SELECT predecessor_id,successor_id,dependency_type FROM pm_activity_dependencies '
            'WHERE project_id=:p ORDER BY predecessor_id,successor_id,dependency_type'),
            {'p': project_id})).mappings().all()
        try:
            calculation = calculate_schedule(
                datetime.fromisoformat(baseline['start_date']).replace(tzinfo=timezone.utc), activities,
                [ActivityDependency(**dict(dependency)) for dependency in dependencies])
        except (SchedulingValidationError, ValueError) as exc:
            raise HTTPException(422, f'Cannot calculate schedule: {exc}') from None

        source = {
            'baseline_id': baseline['id'],
            'baseline_items': [{'entity_id': row['entity_id'], 'snapshot': row['snapshot']} for row in rows],
            'calendar': {'id': calendar_id, 'timezone': calendar_row['timezone'],
                         'weekly_pattern_json': calendar_row['weekly_pattern_json'],
                         'exceptions': [dict(row) for row in exception_rows]},
            'dependencies': [dict(dependency) for dependency in dependencies],
        }
        digest = hashlib.sha256(json.dumps(source, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        number = await self.session.scalar(text(
            'SELECT COALESCE(MAX(version_no),0)+1 FROM pm_schedule_versions WHERE project_id=:p'),
            {'p': project_id})
        version_id = uuid4().hex
        await self.session.execute(text(
            'INSERT INTO pm_schedule_versions('
            'id,project_id,baseline_id,version_no,calculation_inputs_hash,reason,created_by) '
            'VALUES(:id,:p,:b,:n,:h,:r,:u)'),
            {'id': version_id, 'p': project_id, 'b': baseline['id'], 'n': number,
             'h': digest, 'r': payload.reason, 'u': self.request.state.user_id.hex})
        for item in calculation.items:
            await self.session.execute(text(
                'INSERT INTO pm_schedule_items('
                'id,schedule_version_id,project_id,activity_id,scheduling_state,block_reason,'
                'remaining_work_minutes,early_start,early_finish,late_start,late_finish,'
                'total_float_minutes,is_critical) '
                'VALUES(:id,:v,:p,:a,:s,:r,:m,:es,:ef,:ls,:lf,:f,:c)'),
                {'id': uuid4().hex, 'v': version_id, 'p': project_id, 'a': item.activity_id,
                 's': item.scheduling_state, 'r': item.block_reason,
                 'm': work_minutes[item.activity_id],
                 'es': item.early_start.isoformat() if item.early_start else None,
                 'ef': item.early_finish.isoformat() if item.early_finish else None,
                 'ls': item.late_start.isoformat() if item.late_start else None,
                 'lf': item.late_finish.isoformat() if item.late_finish else None,
                 'f': item.total_float_minutes, 'c': int(item.is_critical)})
        self.request.state.audit_details = {
            'entity_type': 'pm.schedule_versions', 'entity_id': str(UUID(version_id)), 'old': None,
            'new': {'status': 'draft', 'baseline_id': baseline['id'], 'version_no': number,
                    'calculation_inputs_hash': digest, 'calculation_state': calculation.state},
            'summary': 'PM schedule draft created'}
        return {'id': version_id, 'version_no': number, 'status': 'draft',
                'calculation_state': calculation.state}

    async def detail(self, project_id, version_id):
        row = await self._version(project_id, version_id)
        items = (await self.session.execute(text(
            'SELECT * FROM pm_schedule_items WHERE schedule_version_id=:v ORDER BY activity_id'),
            {'v': version_id})).mappings()
        return {'version': row, 'items': [dict(item) for item in items]}

    async def propose(self, project_id, version_id):
        row = await self._version(project_id, version_id, 'pm.schedule.propose')
        if row['status'] != 'draft':
            raise HTTPException(409, 'Only draft versions can be proposed')
        active = await self.session.scalar(text(
            "SELECT id FROM pm_schedule_versions WHERE project_id=:p AND status='approved' "
            "ORDER BY version_no DESC,id DESC LIMIT 1"), {'p': project_id})
        stamp = now()
        updated = await self.session.execute(text(
            "UPDATE pm_schedule_versions SET status='proposed',proposed_at=:n,reviewed_against_version_id=:active "
            "WHERE id=:id AND project_id=:p AND status='draft'"),
            {'n': stamp, 'active': active, 'id': version_id, 'p': project_id})
        if updated.rowcount != 1:
            raise HTTPException(409, 'Schedule version changed; reload before proposing')
        self.audit('schedule_versions', version_id, self._decision_context(row),
                   {**self._decision_context(row), 'status': 'proposed', 'proposed_at': stamp,
                    'reviewed_against_version_id': active})
        return {'status': 'proposed'}

    async def approve(self, project_id, version_id, payload=None):
        project = await self.project(project_id, 'pm.schedule.approve')
        # SQLite permits one writer. Acquire it only for the final validation and
        # transition so competing approvals observe the same active-version token.
        if self.session.get_bind().dialect.name == 'sqlite':
            # Authorization above issued reads only. Do not commit an unrelated
            # caller mutation merely to restart the SQLite transaction.
            await self.session.rollback()
            await self.session.execute(text('BEGIN IMMEDIATE'))
        row = (await self.session.execute(text(
            'SELECT * FROM pm_schedule_versions WHERE id=:id AND project_id=:p'),
            {'id': version_id, 'p': project_id})).mappings().first()
        if not row:
            raise HTTPException(404, 'Schedule version not found')
        row = dict(row)
        if row['status'] != 'proposed':
            raise HTTPException(409, 'Only proposed versions can be approved')
        active = await self.session.scalar(text(
            "SELECT id FROM pm_schedule_versions WHERE project_id=:p AND status='approved' "
            "ORDER BY version_no DESC,id DESC LIMIT 1"), {'p': project_id})
        if row.get('reviewed_against_version_id') != active:
            raise HTTPException(409, 'Approved Forecast changed during review; reload and propose again')
        current_hash, actual = await self._current_actual_forecast_hash(project_id, row, project)
        if current_hash and (current_hash != row['calculation_inputs_hash']
                             or actual['input_hash'] != row['actual_input_hash']
                             or actual['output_hash'] != row['actual_output_hash']):
            raise HTTPException(409, 'Forecast inputs changed; recalculate before approval')
        blocked = await self.session.scalar(text(
            "SELECT 1 FROM pm_schedule_items WHERE schedule_version_id=:v "
            "AND scheduling_state LIKE 'blocked_%' LIMIT 1"), {'v': version_id})
        decision_reason = getattr(payload, 'reason', None) if payload else None
        if blocked and not decision_reason:
            raise HTTPException(422, 'A decision reason is required to approve a partial schedule')
        stamp = now()
        superseded = await self.session.execute(text(
            "UPDATE pm_schedule_versions SET status='superseded' "
            "WHERE project_id=:p AND status='approved'"), {'p': project_id})
        updated = await self.session.execute(text(
            "UPDATE pm_schedule_versions SET status='approved',approved_by=:u,approved_at=:n,"
            "effective_from=:n,approval_reason=:r WHERE id=:id AND project_id=:p AND status='proposed'"),
            {'u': self.request.state.user_id.hex, 'n': stamp, 'r': decision_reason,
             'id': version_id, 'p': project_id})
        if updated.rowcount != 1:
            raise HTTPException(409, 'Schedule version changed; reload before approval')
        self.audit('schedule_versions', version_id, self._decision_context(row), {
            **self._decision_context(row), 'status': 'approved', 'approved_by': self.request.state.user_id.hex,
            'approved_at': stamp, 'approval_reason': decision_reason,
            'superseded_versions': superseded.rowcount, 'actual_source_event_ids': json.loads(row['actual_source_event_ids_json'] or '[]')})
        return {'status': 'approved'}

    async def reject(self, project_id, version_id, payload):
        row = await self._version(project_id, version_id, 'pm.schedule.approve')
        if row['status'] != 'proposed':
            raise HTTPException(409, 'Only proposed versions can be rejected')
        stamp = now()
        updated = await self.session.execute(text(
            "UPDATE pm_schedule_versions SET status='rejected',rejected_by=:u,rejected_at=:n,"
            "rejection_reason=:r WHERE id=:id AND project_id=:p AND status='proposed'"),
            {'u': self.request.state.user_id.hex, 'n': stamp, 'r': payload.reason,
             'id': version_id, 'p': project_id})
        if updated.rowcount != 1:
            raise HTTPException(409, 'Schedule version changed; reload before rejection')
        self.audit('schedule_versions', version_id, self._decision_context(row), {
            **self._decision_context(row), 'status': 'rejected', 'rejected_by': self.request.state.user_id.hex,
            'rejected_at': stamp, 'rejection_reason': payload.reason})
        return {'status': 'rejected'}
