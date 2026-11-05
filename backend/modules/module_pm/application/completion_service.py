"""Official PM completion workflow over the existing planning and execution sources."""
import hashlib
import json
from datetime import date
from decimal import Decimal
from pathlib import PurePosixPath
from uuid import UUID, uuid4
from urllib.parse import quote

from fastapi import HTTPException, Response
from sqlalchemy import text

from core.access import allowed
from .planning_service import PlanningService, now
from ..domain.completion import (
    AcceptanceDecision, CloseDecision, IssueCreate, IssueTransition, ReviewDecision,
)


PROJECT_VIEW = 'pm.completion.view'
ISSUE_MANAGE = 'pm.completion.issues.manage'
ISSUE_VERIFY = 'pm.completion.issues.verify'
DOCUMENT_VIEW = 'pm.completion.documents.view'
DOCUMENT_MANAGE = 'pm.completion.documents.manage'
REVIEW = 'pm.completion.review'
ACCEPT = 'pm.completion.accept'
CLOSE = 'pm.completion.close'

TERMINAL_WORK_ORDER_STATES = {'completed', 'closed'}
OPEN_ISSUE_STATES = {'open', 'in_progress', 'resolved'}


class CompletionService(PlanningService):
    async def _case(self, project_id, case_id):
        row = (await self.session.execute(text(
            'SELECT * FROM pm_completion_cases WHERE id=:id AND project_id=:p'),
            {'id': case_id, 'p': project_id})).mappings().first()
        if not row:
            raise HTTPException(404, 'Completion record unavailable')
        return dict(row)

    async def _activity(self, project_id, activity_id):
        row = (await self.session.execute(text(
            'SELECT * FROM pm_activities WHERE id=:a AND project_id=:p AND deleted_at IS NULL'),
            {'a': activity_id, 'p': project_id})).mappings().first()
        if not row:
            raise HTTPException(404, 'Activity unavailable in this project')
        return dict(row)

    async def _activity_execution(self, project_id, activity):
        rows = (await self.session.execute(text(
            "SELECT id,work_order_code,status,actual_quantity_snapshot,completion_date,closure_date "
            "FROM pm_work_orders WHERE project_id=:p AND activity_id=:a AND deleted_at IS NULL ORDER BY created_at,id"),
            {'p': project_id, 'a': activity['id']})).mappings()
        orders = [dict(row) for row in rows]
        counted_orders = [row for row in orders if row['status'] != 'rejected']
        actual = sum((Decimal(row['actual_quantity_snapshot']) for row in counted_orders), Decimal('0'))
        planned = Decimal(activity['planned_quantity'])
        terminal = bool(counted_orders) and all(
            row['status'] in TERMINAL_WORK_ORDER_STATES for row in counted_orders)
        complete = terminal and (planned <= 0 or actual >= planned)
        return {
            'orders': orders,
            'actual_quantity': str(actual),
            'planned_quantity': str(planned),
            'complete': complete,
            'terminal_orders': terminal,
        }

    async def _get_case_for_activity(self, project_id, activity_id):
        row = (await self.session.execute(text(
            "SELECT * FROM pm_completion_cases WHERE project_id=:p AND entity_type='activity' AND entity_id=:a"),
            {'p': project_id, 'a': activity_id})).mappings().first()
        return dict(row) if row else None

    async def _insert_case(self, project_id, entity_type, entity_id, status):
        case_id = uuid4().hex
        stamp = now()
        await self.session.execute(text(
            'INSERT INTO pm_completion_cases '
            '(id,project_id,entity_type,entity_id,status,version,created_at,updated_at) '
            'VALUES (:id,:p,:type,:entity,:status,1,:at,:at)'),
            {'id': case_id, 'p': project_id, 'type': entity_type, 'entity': entity_id,
             'status': status, 'at': stamp})
        return await self._case(project_id, case_id)

    async def _record_event(self, project_id, case_id, action, old_status, new_status, notes='', metadata=None):
        event_id = uuid4().hex
        await self.session.execute(text(
            'INSERT INTO pm_completion_events '
            '(id,project_id,case_id,action,from_status,to_status,actor_user_id,notes,metadata,created_at) '
            'VALUES (:id,:p,:case,:action,:old,:new,:actor,:notes,:metadata,:at)'),
            {'id': event_id, 'p': project_id, 'case': case_id, 'action': action,
             'old': old_status, 'new': new_status, 'actor': self.request.state.user_id.hex,
             'notes': notes, 'metadata': json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True),
             'at': now()})
        return event_id

    async def _transition(self, project_id, case, target, action, notes='', metadata=None):
        result = await self.session.execute(text(
            'UPDATE pm_completion_cases SET status=:target,version=version+1,updated_at=:at '
            'WHERE id=:id AND project_id=:p AND status=:current AND version=:version'),
            {'target': target, 'at': now(), 'id': case['id'], 'p': project_id,
             'current': case['status'], 'version': case['version']})
        if result.rowcount != 1:
            raise HTTPException(409, 'Completion record changed; reload and try again')
        await self._record_event(project_id, case['id'], action, case['status'], target, notes, metadata)
        return await self._case(project_id, case['id'])

    async def _open_blocking_issues(self, project_id, case_id):
        return await self.session.scalar(text(
            "SELECT count(*) FROM pm_completion_issues WHERE project_id=:p AND case_id=:c "
            "AND blocking=1 AND status!='verified'"),
            {'p': project_id, 'c': case_id})

    async def start_review(self, project_id, activity_id):
        await self.project(project_id, REVIEW)
        activity = await self._activity(project_id, activity_id)
        execution = await self._activity_execution(project_id, activity)
        if not execution['complete']:
            raise HTTPException(409, 'Activity execution is not complete; completion is derived from closed work orders and actual quantity')
        case = await self._get_case_for_activity(project_id, activity_id)
        if case and case['status'] != 'requires_treatment':
            raise HTTPException(409, 'Activity is not awaiting review')
        if case and await self._open_blocking_issues(project_id, case['id']):
            raise HTTPException(409, 'Resolve and verify blocking observations before starting the review')
        if case is None:
            case = await self._insert_case(project_id, 'activity', activity_id, 'in_review')
            await self._record_event(project_id, case['id'], 'review_started', None, 'in_review')
            self.request.state.audit_details = {
                'entity_type': 'pm.completion', 'entity_id': activity_id,
                'old': None, 'new': {'status': 'in_review'}, 'summary': 'PM completion review started'}
            return case
        case = await self._transition(project_id, case, 'in_review', 'review_restarted')
        self.request.state.audit_details = {
            'entity_type': 'pm.completion', 'entity_id': activity_id,
            'old': {'status': 'requires_treatment'}, 'new': {'status': 'in_review'},
            'summary': 'PM completion review restarted'}
        return case

    async def review(self, project_id, activity_id, payload: ReviewDecision):
        await self.project(project_id, REVIEW)
        activity = await self._activity(project_id, activity_id)
        execution = await self._activity_execution(project_id, activity)
        if not execution['complete']:
            raise HTTPException(409, 'Activity execution is no longer complete')
        case = await self._get_case_for_activity(project_id, activity_id)
        if not case or case['status'] != 'in_review':
            raise HTTPException(409, 'Start a review before recording its result')
        if payload.result == 'requires_treatment':
            if not payload.missing_requirement or not payload.corrective_action:
                raise HTTPException(422, 'A missing requirement and corrective action are required')
            target = 'requires_treatment'
        else:
            if await self._open_blocking_issues(project_id, case['id']):
                raise HTTPException(409, 'Blocking observations must be verified before review approval')
            target = 'ready_for_acceptance'
        metadata = {'result': payload.result, 'missing_requirement': payload.missing_requirement,
                    'corrective_action': payload.corrective_action,
                    'owner_user_id': payload.owner_user_id.hex if payload.owner_user_id else None,
                    'target_date': payload.target_date.isoformat() if payload.target_date else None}
        case = await self._transition(
            project_id, case, target, 'review_result', payload.notes, metadata)
        if payload.result == 'requires_treatment':
            await self._create_issue(
                project_id, case, IssueCreate(
                    description=payload.missing_requirement,
                    issue_type='review_finding', severity='high', blocking=True,
                    owner_user_id=payload.owner_user_id, target_date=payload.target_date),
                resolution_hint=payload.corrective_action)
        self.request.state.audit_details = {
            'entity_type': 'pm.completion', 'entity_id': activity_id,
            'old': {'status': 'in_review'}, 'new': {'status': target, 'review': metadata},
            'summary': 'PM completion review decision'}
        return case

    async def accept(self, project_id, activity_id, payload: AcceptanceDecision):
        await self.project(project_id, ACCEPT)
        await self._activity(project_id, activity_id)
        case = await self._get_case_for_activity(project_id, activity_id)
        if not case or case['status'] != 'ready_for_acceptance':
            raise HTTPException(409, 'Successful completion review is required before acceptance')
        if await self._open_blocking_issues(project_id, case['id']):
            raise HTTPException(409, 'Blocking observations prevent acceptance')
        if payload.result == 'rejected':
            if not payload.notes:
                raise HTTPException(422, 'A rejection reason is required')
            target = 'requires_treatment'
        else:
            target = 'accepted'
        metadata = {'result': payload.result, 'acceptance_type': payload.acceptance_type,
                    'reference': payload.reference, 'received_at': now()}
        case = await self._transition(
            project_id, case, target, 'acceptance_decision', payload.notes, metadata)
        if payload.result == 'rejected':
            await self._create_issue(
                project_id, case, IssueCreate(
                    description=payload.notes, issue_type='acceptance_rejection',
                    severity='high', blocking=True))
        self.request.state.audit_details = {
            'entity_type': 'pm.completion', 'entity_id': activity_id,
            'old': {'status': 'ready_for_acceptance'},
            'new': {'status': target, 'acceptance': metadata},
            'summary': 'PM acceptance decision'}
        return case

    async def close_project(self, project_id, payload: CloseDecision):
        project = await self.project(project_id, CLOSE)
        if (await self.session.scalar(text(
            "SELECT 1 FROM pm_completion_cases WHERE project_id=:p AND entity_type='project'"),
            {'p': project_id})):
            raise HTTPException(409, 'Project has already been officially closed')
        rows = (await self.session.execute(text(
            'SELECT a.id,a.planned_quantity,a.name,a.activity_code,t.id AS task_id,t.phase_id '
            'FROM pm_activities a JOIN pm_tasks t ON t.id=a.task_id AND t.project_id=a.project_id '
            'AND t.deleted_at IS NULL JOIN pm_phases ph ON ph.id=t.phase_id AND ph.project_id=t.project_id '
            'AND ph.deleted_at IS NULL WHERE a.project_id=:p AND a.deleted_at IS NULL ORDER BY ph.name,t.name,a.name'),
            {'p': project_id})).mappings()
        activities = [dict(row) for row in rows]
        if not activities:
            raise HTTPException(409, 'Project has no active activities to close')
        phase_count = await self.session.scalar(text(
            'SELECT count(*) FROM pm_phases WHERE project_id=:p AND deleted_at IS NULL'),
            {'p': project_id})
        task_count = await self.session.scalar(text(
            'SELECT count(*) FROM pm_tasks WHERE project_id=:p AND deleted_at IS NULL'),
            {'p': project_id})
        empty_phases = await self.session.scalar(text(
            'SELECT count(*) FROM pm_phases ph WHERE ph.project_id=:p AND ph.deleted_at IS NULL '
            'AND NOT EXISTS (SELECT 1 FROM pm_tasks t WHERE t.phase_id=ph.id AND t.project_id=ph.project_id '
            'AND t.deleted_at IS NULL)'), {'p': project_id})
        empty_tasks = await self.session.scalar(text(
            'SELECT count(*) FROM pm_tasks t WHERE t.project_id=:p AND t.deleted_at IS NULL '
            'AND NOT EXISTS (SELECT 1 FROM pm_activities a WHERE a.task_id=t.id AND a.project_id=t.project_id '
            'AND a.deleted_at IS NULL)'), {'p': project_id})
        if not phase_count or not task_count or empty_phases or empty_tasks:
            raise HTTPException(409, 'Every active phase and task must contain work before project closure')
        task_activity_counts = {}
        phase_task_counts = {}
        for activity in activities:
            execution = await self._activity_execution(project_id, activity)
            if not execution['complete']:
                raise HTTPException(409, f"Activity {activity['activity_code']} is not execution-complete")
            task_activity_counts[activity['task_id']] = task_activity_counts.get(activity['task_id'], 0) + 1
            phase_task_counts.setdefault(activity['phase_id'], set()).add(activity['task_id'])
            case = await self._get_case_for_activity(project_id, activity['id'])
            if not case or case['status'] != 'accepted':
                raise HTTPException(409, f"Activity {activity['activity_code']} must be accepted before project closure")
            if await self._open_blocking_issues(project_id, case['id']):
                raise HTTPException(409, f"Activity {activity['activity_code']} has blocking observations")
            has_receipt = await self.session.scalar(text(
                "SELECT 1 FROM pm_completion_events WHERE project_id=:p AND case_id=:c "
                "AND action='acceptance_decision' AND to_status='accepted'"),
                {'p': project_id, 'c': case['id']})
            if not has_receipt:
                raise HTTPException(409, f"Activity {activity['activity_code']} is missing its acceptance record")
            has_closeout_document = await self.session.scalar(text(
                "SELECT 1 FROM pm_completion_attachments WHERE project_id=:p AND case_id=:c "
                "AND category='closeout_document'"),
                {'p': project_id, 'c': case['id']})
            if not has_closeout_document:
                raise HTTPException(
                    409, f"Activity {activity['activity_code']} is missing a required close-out document")
        if len(task_activity_counts) != task_count or len(phase_task_counts) != phase_count:
            raise HTTPException(409, 'The project completion hierarchy is incomplete')
        project_case = await self._insert_case(project_id, 'project', project_id, 'closed')
        for activity in activities:
            case = await self._get_case_for_activity(project_id, activity['id'])
            await self._transition(project_id, case, 'closed', 'project_close', payload.reason,
                                   {'project_id': project_id})
        await self._record_event(
            project_id, project_case['id'], 'project_closed', None, 'closed', payload.reason,
            {'project_code': project['project_code'], 'activity_count': len(activities),
             'closed_at': now()})
        self.request.state.audit_details = {
            'entity_type': 'pm.completion', 'entity_id': project_id, 'old': None,
            'new': {'status': 'closed', 'activity_count': len(activities), 'reason': payload.reason},
            'summary': 'PM project officially closed'}
        return {'status': 'closed', 'closed_activities': len(activities)}

    async def _create_issue(self, project_id, case, payload: IssueCreate, resolution_hint=''):
        issue_id = uuid4().hex
        owner_id = payload.owner_user_id.hex if payload.owner_user_id else None
        if owner_id:
            organization = await self.session.scalar(
                text('SELECT organization_id FROM pm_projects WHERE id=:p'), {'p': project_id})
            user_exists = await self.session.scalar(text(
                'SELECT 1 FROM users WHERE id=:id AND is_active=1 AND organization_id=:org'),
                {'id': owner_id, 'org': organization})
            if not user_exists:
                raise HTTPException(422, 'Observation owner must be active in the project organization')
        await self.session.execute(text(
            'INSERT INTO pm_completion_issues '
            '(id,project_id,case_id,description,issue_type,severity,blocking,owner_user_id,target_date,status,'
            'resolution_notes,created_by,created_at,updated_at) '
            "VALUES (:id,:p,:c,:description,:type,:severity,:blocking,:owner,:due,'open',:hint,:actor,:at,:at)"),
            {'id': issue_id, 'p': project_id, 'c': case['id'], 'description': payload.description,
             'type': payload.issue_type, 'severity': payload.severity, 'blocking': int(payload.blocking),
             'owner': owner_id, 'due': payload.target_date.isoformat() if payload.target_date else None,
             'hint': resolution_hint, 'actor': self.request.state.user_id.hex, 'at': now()})
        if payload.blocking and case['status'] == 'ready_for_acceptance':
            await self._transition(project_id, case, 'requires_treatment', 'blocking_issue_added',
                                   payload.description, {'issue_id': issue_id})
        return issue_id

    async def create_issue(self, project_id, case_id, payload: IssueCreate):
        await self.project(project_id, ISSUE_MANAGE)
        case = await self._case(project_id, case_id)
        if case['entity_type'] != 'activity' or case['status'] not in (
                'in_review', 'ready_for_acceptance', 'requires_treatment'):
            raise HTTPException(409, 'Observations can only be added to an active activity review')
        issue_id = await self._create_issue(project_id, case, payload)
        self.request.state.audit_details = {
            'entity_type': 'pm.completion_issue', 'entity_id': issue_id,
            'old': None, 'new': payload.model_dump(mode='json'), 'summary': 'PM completion observation created'}
        row = await self._issue(project_id, issue_id)
        return row

    async def _issue(self, project_id, issue_id):
        row = (await self.session.execute(text(
            'SELECT i.*,u.full_name AS owner_name FROM pm_completion_issues i '
            'LEFT JOIN users u ON u.id=i.owner_user_id WHERE i.id=:id AND i.project_id=:p'),
            {'id': issue_id, 'p': project_id})).mappings().first()
        if not row:
            raise HTTPException(404, 'Observation unavailable')
        return dict(row)

    async def transition_issue(self, project_id, issue_id, target, payload: IssueTransition):
        permission = ISSUE_VERIFY if target == 'verified' else ISSUE_MANAGE
        await self.project(project_id, permission)
        issue = await self._issue(project_id, issue_id)
        transitions = {'open': {'in_progress'}, 'in_progress': {'resolved'}, 'resolved': {'verified'}}
        if target not in transitions.get(issue['status'], set()):
            raise HTTPException(409, 'Invalid observation transition')
        if target == 'resolved':
            evidence = await self.session.scalar(text(
                "SELECT 1 FROM pm_completion_attachments WHERE project_id=:p AND case_id=:c "
                "AND issue_id=:i AND category='issue_evidence'"),
                {'p': project_id, 'c': issue['case_id'], 'i': issue_id})
            if not evidence:
                raise HTTPException(409, 'Attach resolution evidence before marking the observation resolved')
        result = await self.session.execute(text(
            'UPDATE pm_completion_issues SET status=:target,updated_at=:at,'
            'resolution_notes=CASE WHEN :target=:resolved THEN :notes ELSE resolution_notes END,'
            'verified_by=CASE WHEN :target=:verified THEN :actor ELSE verified_by END,'
            'verified_at=CASE WHEN :target=:verified THEN :at ELSE verified_at END '
            'WHERE id=:id AND project_id=:p AND status=:current'),
            {'target': target, 'resolved': 'resolved', 'verified': 'verified', 'notes': payload.notes,
             'actor': self.request.state.user_id.hex, 'at': now(), 'id': issue_id,
             'p': project_id, 'current': issue['status']})
        if result.rowcount != 1:
            raise HTTPException(409, 'Observation changed; reload and try again')
        await self._record_event(project_id, issue['case_id'], 'issue_' + target, issue['status'], target,
                                 payload.notes, {'issue_id': issue_id})
        self.request.state.audit_details = {
            'entity_type': 'pm.completion_issue', 'entity_id': issue_id,
            'old': {'status': issue['status']}, 'new': {'status': target, 'notes': payload.notes},
            'summary': 'PM completion observation ' + target}
        return await self._issue(project_id, issue_id)

    async def workspace(self, project_id):
        await self.project(project_id, PROJECT_VIEW)
        project = await self.repo.get('projects', project_id)
        phase_rows = (await self.session.execute(text(
            'SELECT id,phase_code,name FROM pm_phases WHERE project_id=:p AND deleted_at IS NULL ORDER BY name,id'),
            {'p': project_id})).mappings()
        task_rows = (await self.session.execute(text(
            'SELECT id,phase_id,task_code,name FROM pm_tasks WHERE project_id=:p AND deleted_at IS NULL ORDER BY name,id'),
            {'p': project_id})).mappings()
        activity_rows = (await self.session.execute(text(
            'SELECT id,task_id,activity_code,name,planned_quantity,unit,planned_start_date,planned_end_date '
            'FROM pm_activities WHERE project_id=:p AND deleted_at IS NULL ORDER BY name,id'),
            {'p': project_id})).mappings()
        cases = (await self.session.execute(text(
            'SELECT * FROM pm_completion_cases WHERE project_id=:p ORDER BY created_at,id'),
            {'p': project_id})).mappings()
        case_by_entity = {(row['entity_type'], row['entity_id']): dict(row) for row in cases}
        issues = (await self.session.execute(text(
            'SELECT i.*,u.full_name AS owner_name FROM pm_completion_issues i '
            'LEFT JOIN users u ON u.id=i.owner_user_id WHERE i.project_id=:p ORDER BY i.created_at,i.id'),
            {'p': project_id})).mappings()
        events = (await self.session.execute(text(
            'SELECT e.*,u.full_name AS actor_name FROM pm_completion_events e '
            'JOIN users u ON u.id=e.actor_user_id WHERE e.project_id=:p ORDER BY e.created_at,e.id'),
            {'p': project_id})).mappings()
        documents = (await self.session.execute(text(
            'SELECT id,case_id,issue_id,category,filename,content_type,size,sha256,created_by,created_at '
            'FROM pm_completion_attachments WHERE project_id=:p ORDER BY created_at,id'),
            {'p': project_id})).mappings()
        closeout_document_cases = {
            row['case_id'] for row in documents if row['category'] == 'closeout_document'}
        if not allowed(self.request, DOCUMENT_VIEW):
            documents = []
        orders = (await self.session.execute(text(
            "SELECT id,activity_id,work_order_code,status,actual_quantity_snapshot,completion_date,closure_date "
            "FROM pm_work_orders WHERE project_id=:p AND deleted_at IS NULL ORDER BY created_at,id"),
            {'p': project_id})).mappings()
        orders_by_activity = {}
        for row in orders:
            orders_by_activity.setdefault(row['activity_id'], []).append(dict(row))

        issues_by_case = {}
        for row in issues:
            issues_by_case.setdefault(row['case_id'], []).append(dict(row))
        events_by_case = {}
        for row in events:
            item = dict(row)
            item['metadata'] = json.loads(item['metadata'])
            events_by_case.setdefault(row['case_id'], []).append(item)
        documents_by_case = {}
        for row in documents:
            item = dict(row)
            documents_by_case.setdefault(row['case_id'], []).append(item)

        tasks_by_phase = {}
        for row in task_rows:
            tasks_by_phase.setdefault(row['phase_id'], []).append(dict(row))
        activities_by_task = {}
        completion_counts = {
            'eligible': 0, 'review': 0, 'accepted': 0, 'issues': 0,
            'blocking_issues': 0, 'closed': 0,
        }
        for row in activity_rows:
            activity = dict(row)
            activity_orders = orders_by_activity.get(activity['id'], [])
            counted_orders = [item for item in activity_orders if item['status'] != 'rejected']
            actual = sum((Decimal(item['actual_quantity_snapshot']) for item in counted_orders), Decimal('0'))
            planned = Decimal(activity['planned_quantity'])
            terminal = bool(counted_orders) and all(
                item['status'] in TERMINAL_WORK_ORDER_STATES for item in counted_orders)
            execution_complete = terminal and (planned <= 0 or actual >= planned)
            case = case_by_entity.get(('activity', activity['id']))
            case_id = case['id'] if case else None
            activity.update({
                'actual_quantity': str(actual), 'execution_complete': execution_complete,
                'work_orders': activity_orders, 'case': case,
                'issues': issues_by_case.get(case_id, []) if case_id else [],
                'events': events_by_case.get(case_id, []) if case_id else [],
                'documents': documents_by_case.get(case_id, []) if case_id else [],
                'has_closeout_document': case_id in closeout_document_cases,
            })
            if execution_complete:
                completion_counts['eligible'] += 1
            if case and case['status'] in ('in_review', 'requires_treatment'):
                completion_counts['review'] += 1
            if case and case['status'] in ('accepted', 'closed'):
                completion_counts['accepted'] += 1
            if case and case['status'] == 'closed':
                completion_counts['closed'] += 1
            completion_counts['issues'] += sum(
                issue['status'] != 'verified' for issue in activity['issues'])
            completion_counts['blocking_issues'] += sum(
                bool(issue['blocking']) and issue['status'] != 'verified'
                for issue in activity['issues'])
            activities_by_task.setdefault(activity['task_id'], []).append(activity)

        for task in (task for values in tasks_by_phase.values() for task in values):
            task['activities'] = activities_by_task.get(task['id'], [])
            task['execution_complete'] = bool(task['activities']) and all(
                activity['execution_complete'] for activity in task['activities'])
            task['completion_complete'] = bool(task['activities']) and all(
                activity.get('case') and activity['case']['status'] == 'closed'
                for activity in task['activities'])
        phases = []
        for phase_row in phase_rows:
            phase = dict(phase_row)
            phase['tasks'] = tasks_by_phase.get(phase['id'], [])
            phase['execution_complete'] = bool(phase['tasks']) and all(
                task['execution_complete'] for task in phase['tasks'])
            phase['completion_complete'] = bool(phase['tasks']) and all(
                task['completion_complete'] for task in phase['tasks'])
            phases.append(phase)
        project_execution_complete = bool(phases) and all(phase['execution_complete'] for phase in phases)
        active_activities = [
            activity for phase in phases for task in phase['tasks'] for activity in task['activities']]
        documents_complete = bool(active_activities) and all(
            activity['has_closeout_document'] for activity in active_activities)
        project_case = case_by_entity.get(('project', project_id))
        project_closed = bool(project_case and project_case['status'] == 'closed')
        return {
            'project': {**project, 'phases': phases},
            'project_execution_complete': project_execution_complete,
            'documents_complete': documents_complete,
            'project_closed': project_closed,
            'project_case': project_case,
            'project_events': events_by_case.get(project_case['id'], []) if project_case else [],
            'counts': completion_counts,
            'issues': [dict(row) for row in issues],
            'events': [dict(row) for row in events],
            'documents': [dict(row) for row in documents],
        }

    async def center(self):
        from ..domain.planning import in_scope
        from core.access import require

        require(self.request, PROJECT_VIEW)
        projects = [
            row for row in await self.repo.rows('projects')
            if not row['deleted_at'] and in_scope(
                row, self.request.state.user, self.request.state.is_admin,
                self.request.state.permission_scopes.get(PROJECT_VIEW, {'self'}))
        ]
        if not projects:
            return {'items': []}
        project_ids = [row['id'] for row in projects]
        binds = {f'p{index}': project_id for index, project_id in enumerate(project_ids)}
        placeholders = ','.join(':' + key for key in binds)
        activities = (await self.session.execute(text(
            f'SELECT id,project_id,planned_quantity FROM pm_activities '
            f'WHERE project_id IN ({placeholders}) AND deleted_at IS NULL'),
            binds)).mappings()
        activity_rows = [dict(row) for row in activities]
        active_activity_counts = (await self.session.execute(text(
            f'SELECT project_id,count(*) AS count FROM pm_activities WHERE project_id IN ({placeholders}) '
            'AND deleted_at IS NULL GROUP BY project_id'), binds)).mappings()
        phase_counts = (await self.session.execute(text(
            f'SELECT project_id,count(*) AS count FROM pm_phases WHERE project_id IN ({placeholders}) '
            'AND deleted_at IS NULL GROUP BY project_id'), binds)).mappings()
        task_counts = (await self.session.execute(text(
            f'SELECT project_id,count(*) AS count FROM pm_tasks WHERE project_id IN ({placeholders}) '
            'AND deleted_at IS NULL GROUP BY project_id'), binds)).mappings()
        hierarchy_activity_counts = (await self.session.execute(text(
            f'SELECT a.project_id,count(*) AS count FROM pm_activities a '
            'JOIN pm_tasks t ON t.id=a.task_id AND t.project_id=a.project_id AND t.deleted_at IS NULL '
            'JOIN pm_phases ph ON ph.id=t.phase_id AND ph.project_id=t.project_id AND ph.deleted_at IS NULL '
            f'WHERE a.project_id IN ({placeholders}) AND a.deleted_at IS NULL GROUP BY a.project_id'),
            binds)).mappings()
        active_activity_counts = {row['project_id']: row['count'] for row in active_activity_counts}
        phase_counts = {row['project_id']: row['count'] for row in phase_counts}
        task_counts = {row['project_id']: row['count'] for row in task_counts}
        hierarchy_activity_counts = {
            row['project_id']: row['count'] for row in hierarchy_activity_counts}
        empty_phase_rows = (await self.session.execute(text(
            f'SELECT ph.project_id,count(*) AS count FROM pm_phases ph WHERE ph.project_id IN ({placeholders}) '
            'AND ph.deleted_at IS NULL AND NOT EXISTS (SELECT 1 FROM pm_tasks t WHERE t.phase_id=ph.id '
            'AND t.project_id=ph.project_id AND t.deleted_at IS NULL) GROUP BY ph.project_id'), binds)).mappings()
        empty_task_rows = (await self.session.execute(text(
            f'SELECT t.project_id,count(*) AS count FROM pm_tasks t WHERE t.project_id IN ({placeholders}) '
            'AND t.deleted_at IS NULL AND NOT EXISTS (SELECT 1 FROM pm_activities a WHERE a.task_id=t.id '
            'AND a.project_id=t.project_id AND a.deleted_at IS NULL) GROUP BY t.project_id'), binds)).mappings()
        empty_phases = {row['project_id']: row['count'] for row in empty_phase_rows}
        empty_tasks = {row['project_id']: row['count'] for row in empty_task_rows}
        activity_ids = [row['id'] for row in activity_rows]
        execution = {}
        if activity_ids:
            activity_binds = {f'a{index}': activity_id for index, activity_id in enumerate(activity_ids)}
            order_rows = (await self.session.execute(text(
                f"SELECT activity_id,status,actual_quantity_snapshot FROM pm_work_orders "
                f"WHERE activity_id IN ({','.join(':' + key for key in activity_binds)}) "
                "AND deleted_at IS NULL AND status!='rejected'"),
                activity_binds)).mappings()
            for row in order_rows:
                execution.setdefault(row['activity_id'], []).append(dict(row))
        cases = (await self.session.execute(text(
            f'SELECT project_id,entity_type,entity_id,status FROM pm_completion_cases '
            f'WHERE project_id IN ({placeholders})'), binds)).mappings()
        case_rows = [dict(row) for row in cases]
        issues = (await self.session.execute(text(
            f"SELECT project_id,count(*) AS count,"
            f"sum(CASE WHEN blocking=1 THEN 1 ELSE 0 END) AS blockers "
            f"FROM pm_completion_issues "
            f"WHERE project_id IN ({placeholders}) AND status!='verified' GROUP BY project_id"),
            binds)).mappings()
        issue_counts = {row['project_id']: row['count'] for row in issues}
        blocker_counts = {row['project_id']: row['blockers'] for row in issues}
        closeout_document_counts = (await self.session.execute(text(
            f"SELECT c.project_id,count(DISTINCT c.entity_id) AS count "
            f"FROM pm_completion_cases c JOIN pm_completion_attachments d "
            "ON d.project_id=c.project_id AND d.case_id=c.id AND d.category='closeout_document' "
            f"WHERE c.project_id IN ({placeholders}) AND c.entity_type='activity' GROUP BY c.project_id"),
            binds)).mappings()
        closeout_documents = {row['project_id']: row['count'] for row in closeout_document_counts}
        activities_by_project = {}
        for activity in activity_rows:
            orders = execution.get(activity['id'], [])
            actual = sum((Decimal(order['actual_quantity_snapshot']) for order in orders), Decimal('0'))
            planned = Decimal(activity['planned_quantity'])
            activity['complete'] = (
                bool(orders)
                and all(order['status'] in TERMINAL_WORK_ORDER_STATES for order in orders)
                and (planned <= 0 or actual >= planned)
            )
            activities_by_project.setdefault(activity['project_id'], []).append(activity)
        cases_by_activity = {
            row['entity_id']: row for row in case_rows if row['entity_type'] == 'activity'
        }
        project_closed = {
            row['project_id']: row['status'] == 'closed'
            for row in case_rows if row['entity_type'] == 'project'
        }
        items = []
        for project in projects:
            activities = activities_by_project.get(project['id'], [])
            complete = (
                bool(activities)
                and all(row['complete'] for row in activities)
                and len(activities) == active_activity_counts.get(project['id'], 0)
                and len(activities) == hierarchy_activity_counts.get(project['id'], 0)
                and phase_counts.get(project['id'], 0) > 0
                and task_counts.get(project['id'], 0) > 0
                and not empty_phases.get(project['id'], 0)
                and not empty_tasks.get(project['id'], 0)
            )
            reviewed = sum(
                cases_by_activity.get(row['id'], {}).get('status') in
                ('ready_for_acceptance', 'accepted', 'closed')
                for row in activities
            )
            accepted = sum(
                cases_by_activity.get(row['id'], {}).get('status') in ('accepted', 'closed')
                for row in activities
            )
            items.append({
                'id': project['id'], 'name': project['name'], 'project_code': project['project_code'],
                'status': project['status'], 'activity_count': len(activities),
                'executively_complete': sum(row['complete'] for row in activities),
                'reviews_complete': reviewed, 'accepted': accepted,
                'open_issues': issue_counts.get(project['id'], 0),
                'blocking_issues': blocker_counts.get(project['id'], 0),
                'project_closed': project_closed.get(project['id'], False),
                'ready_for_review': bool(
                    complete and project['status'] == 'in_progress'
                    and not blocker_counts.get(project['id'], 0)
                    and not project_closed.get(project['id'], False)
                    and (self.request.state.is_admin or (
                        REVIEW in self.request.state.permissions and in_scope(
                            project, self.request.state.user, self.request.state.is_admin,
                            self.request.state.permission_scopes.get(REVIEW, {'self'}))
                    ))
                ),
                'documents_complete': closeout_documents.get(project['id'], 0) == len(activities),
                'closeable': complete and accepted == len(activities)
                and closeout_documents.get(project['id'], 0) == len(activities)
                and not blocker_counts.get(project['id'], 0),
            })
        return {'items': items}

    async def list_documents(self, project_id, case_id):
        await self.project(project_id, DOCUMENT_VIEW)
        await self._case(project_id, case_id)
        rows = (await self.session.execute(text(
            'SELECT id,case_id,issue_id,category,filename,content_type,size,sha256,created_by,created_at '
            'FROM pm_completion_attachments WHERE project_id=:p AND case_id=:c ORDER BY created_at,id'),
            {'p': project_id, 'c': case_id})).mappings()
        return {'items': [dict(row) for row in rows]}

    async def upload_document(self, project_id, case_id, category, file, issue_id=None):
        await self.project(project_id, DOCUMENT_MANAGE)
        case = await self._case(project_id, case_id)
        if case['status'] == 'closed':
            raise HTTPException(409, 'Documents cannot be added after official closure')
        if category == 'issue_evidence':
            if not issue_id:
                raise HTTPException(422, 'Issue evidence must be linked to an observation')
            issue = await self._issue(project_id, issue_id)
            if issue['case_id'] != case_id:
                raise HTTPException(422, 'Observation must belong to the selected completion record')
        elif issue_id:
            raise HTTPException(422, 'Only issue evidence can be linked to an observation')
        data = await file.read(5242881)
        if not data or len(data) > 5242880:
            raise HTTPException(422, 'File size must be between 1 byte and 5 MB')
        filename = PurePosixPath((file.filename or '').replace('\\', '/')).name
        if not filename or len(filename) > 200 or any(ord(char) < 32 for char in filename):
            raise HTTPException(422, 'Invalid filename')
        suffix = PurePosixPath(filename).suffix.lower()
        mime = None
        if suffix == '.pdf' and data.startswith(b'%PDF-'):
            mime = 'application/pdf'
        elif suffix == '.png' and data.startswith(b'\x89PNG\r\n\x1a\n'):
            mime = 'image/png'
        elif suffix in ('.jpg', '.jpeg') and data.startswith(b'\xff\xd8\xff'):
            mime = 'image/jpeg'
        elif suffix in ('.txt', '.csv'):
            try:
                data.decode('utf-8-sig')
                if b'\0' not in data:
                    mime = 'text/plain'
            except UnicodeDecodeError:
                mime = None
        if not mime:
            raise HTTPException(422, 'Accepted file types: PDF, PNG, JPEG, UTF-8 TXT or CSV')
        identifier = uuid4().hex
        stamp = now()
        metadata = {
            'id': identifier, 'project_id': project_id, 'case_id': case_id,
            'issue_id': issue_id, 'category': category, 'filename': filename,
            'content_type': mime, 'size': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
            'content': data, 'created_by': self.request.state.user_id.hex, 'created_at': stamp,
        }
        await self.session.execute(text(
            'INSERT INTO pm_completion_attachments '
            '(id,project_id,case_id,issue_id,category,filename,content_type,size,sha256,content,created_by,created_at) '
            'VALUES (:id,:project_id,:case_id,:issue_id,:category,:filename,:content_type,:size,:sha256,:content,:created_by,:created_at)'),
            metadata)
        self.request.state.audit_details = {
            'entity_type': 'pm.completion_attachment', 'entity_id': identifier,
            'old': None, 'new': {key: value for key, value in metadata.items() if key != 'content'},
            'summary': 'PM completion evidence uploaded'}
        return {key: value for key, value in metadata.items() if key != 'content'}

    async def download_document(self, project_id, case_id, attachment_id):
        await self.project(project_id, DOCUMENT_VIEW)
        await self._case(project_id, case_id)
        row = (await self.session.execute(text(
            'SELECT filename,content_type,content FROM pm_completion_attachments '
            'WHERE id=:id AND project_id=:p AND case_id=:c'),
            {'id': attachment_id, 'p': project_id, 'c': case_id})).mappings().first()
        if not row:
            raise HTTPException(404, 'Completion document unavailable')
        return Response(bytes(row['content']), media_type=row['content_type'], headers={
            'Content-Disposition': "attachment; filename*=UTF-8''" + quote(row['filename'], safe=''),
            'X-Content-Type-Options': 'nosniff', 'Cache-Control': 'no-store'})
