"""Scoped display references for PM forms; no new authorization service."""
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy import bindparam, text

from infrastructure.database.db_context import get_session
from ..application.planning_service import PlanningService
from ..domain.planning import in_scope
from core.access import require
from ..application.completion_service import CompletionService
from ..application.planning_workflow import PlanningWorkflow

router = APIRouter(prefix='/api/v1/pm', tags=['PM references'])
Section = Literal['baselines', 'dependencies', 'risks', 'deviations', 'cashflows',
                  'communications', 'reports', 'work-orders', 'weekly-plans', 'completion']


def section_permission(section):
    return {'risks':'pm.risks.view', 'reports':'pm.reports.view',
            'work-orders':'pm.execution.view', 'weekly-plans':'pm.wep.view',
            'completion':'pm.completion.view'}.get(section,'pm.planning.view')


@router.get('/completion-center')
async def completion_center(request: Request, session=Depends(get_session, scope='function')):
    return await CompletionService(session, request).center()


@router.get('/execution-center-projects')
async def execution_center_projects(request: Request, session=Depends(get_session, scope='function')):
    code = 'pm.execution.view'
    require(request, code)
    service = PlanningService(session, request)
    rows = [
        row for row in await service.repo.rows('projects')
        if not row['deleted_at']
        and row['status'] in ('planned', 'in_progress')
        and in_scope(
            row, request.state.user, request.state.is_admin,
            request.state.permission_scopes.get(code, {'self'}),
        )
    ]
    planned_ids = [row['id'] for row in rows if row['status'] == 'planned']
    activities_by_project = {}
    if planned_ids:
        statement = text(
            'SELECT project_id,approval_status FROM pm_activities '
            'WHERE deleted_at IS NULL AND project_id IN :project_ids'
        ).bindparams(bindparam('project_ids', expanding=True))
        activities = (await session.execute(statement, {'project_ids': planned_ids})).mappings()
        for activity in activities:
            activities_by_project.setdefault(activity['project_id'], []).append(dict(activity))
    ready_ids = {
        project_id for project_id, activities in activities_by_project.items()
        if PlanningWorkflow.activities_ready_for_execution(activities)
    }
    items = [
        {
            'id': row['id'], 'name': row['name'], 'project_code': row['project_code'],
            'start_date': row.get('start_date'), 'status': row['status'],
        }
        for row in rows
        if row['status'] == 'in_progress' or row['id'] in ready_ids
    ]
    return {'items': items}


@router.get('/ui-projects')
async def projects(request: Request, section: Section, session=Depends(get_session, scope='function')):
    code = section_permission(section)
    require(request,code)
    rows = await PlanningService(session,request).repo.rows('projects')
    scopes = request.state.permission_scopes.get(code,{'self'})
    return {'items':[{'id':r['id'],'name':r['name'],'project_code':r['project_code'],
                      'start_date':r.get('start_date'), 'status':r.get('status')} for r in rows
        if not r['deleted_at'] and in_scope(r,request.state.user,request.state.is_admin,scopes)]}


@router.get('/projects/{project_id}/ui-references')
async def references(project_id: UUID, request: Request,
                     section: Section,
                     session=Depends(get_session, scope='function')):
    from modules.module_currency.application.currency_service import CurrencyService
    permission = section_permission(section)
    project = await PlanningService(session, request).project(project_id.hex, permission)
    calendar_id = project.get('default_schedule_calendar_id')
    schedule_calendar_name = ''
    if calendar_id:
        schedule_calendar_name = await session.scalar(
            text(
                'SELECT name FROM pm_schedule_calendars '
                'WHERE id=:id AND project_id=:project_id AND is_active=1 AND deleted_at IS NULL'
            ),
            {
                'id': calendar_id,
                'project_id': project['id'],
            },
        ) or ''
    result = {'project': {
        'id': project['id'],
        'project_code': project['project_code'],
        'name': project['name'],
        'currency': project['currency'],
        'organization_id': project['organization_id'],
        'start_date': project['start_date'],
        'status': project['status'],
        'client_name': project.get('client_name') or '',
        'default_schedule_calendar_id': calendar_id,
        'schedule_calendar_name': schedule_calendar_name,
        'manager_name': await session.scalar(
            text('SELECT full_name FROM users WHERE id=:id'),
            {'id': project['project_manager_user_id']},
        ) or '',
        'organization_name': await session.scalar(
            text('SELECT name FROM organizations WHERE id=:id'),
            {'id': project['organization_id']},
        ) or '',
    }}
    for kind in ('phases', 'tasks', 'activities'):
        if kind == 'activities' and section in ('work-orders', 'weekly-plans'):
            query = text(
                'SELECT a.id,a.name,a.planned_quantity,a.unit,a.planned_start_date,a.planned_end_date,'
                'a.approval_status,a.activity_code,'
                't.name AS task_name,ph.name AS phase_name '
                'FROM pm_activities a '
                'JOIN pm_tasks t ON t.id=a.task_id AND t.project_id=a.project_id AND t.deleted_at IS NULL '
                'JOIN pm_phases ph ON ph.id=t.phase_id AND ph.project_id=t.project_id AND ph.deleted_at IS NULL '
                'WHERE a.project_id=:p AND a.deleted_at IS NULL ORDER BY a.name'
            )
            params = {'p': project_id.hex}
        else:
            query = text(
                f'SELECT id,name FROM pm_{kind} WHERE project_id=:p AND deleted_at IS NULL ORDER BY name')
            params = {'p': project_id.hex}
        rows = (await session.execute(query, params)).mappings()
        result[kind] = [dict(row) for row in rows]
    users = (await session.execute(text(
        'SELECT id,full_name AS name FROM users WHERE is_active=1 AND organization_id=:org ORDER BY full_name'),
        {'org': project['organization_id']})).mappings()
    result['users'] = [dict(row) for row in users]
    result['currencies'] = [{'id': c.code, 'name': c.name} for c in await CurrencyService(session).repo.list_currencies()]
    return result
