from uuid import UUID
import re
from typing import Literal
from sqlalchemy import text
from fastapi import APIRouter, Depends, Request, Query
from core.access import require
from infrastructure.database.db_context import get_session
from ..domain.planning import KINDS, cost, in_scope
from ..application.planning_service import PlanningService, permission

router = APIRouter(prefix='/api/v1/pm', tags=['PM planning'])
Session = Depends(get_session, scope='function')


@router.get('/projects/{project_id}/planning-rate')
async def planning_rate(project_id: UUID, request: Request, source: str, destination: str,
                        rate_date: str, quantity: str | None = None,
                        unit_price: str | None = None, session=Session):
    from datetime import date
    from modules.module_currency.application.currency_service import CurrencyService
    await PlanningService(session, request).project(project_id.hex, 'pm.planning.manage')
    try:
        date.fromisoformat(rate_date)
    except ValueError:
        from fastapi import HTTPException
        raise HTTPException(422, 'تاريخ المصارفة غير صالح') from None
    result = await CurrencyService(session).get_anchor_snapshot(source, destination, rate_date, 'YER')
    result['rate'] = str(result['rate']) if result['rate'] is not None else None
    if result.get('available') and quantity not in (None, '') and unit_price not in (None, ''):
        try:
            result['planned_cost'] = str(cost(quantity, unit_price, result['rate']))
        except Exception:
            result['planned_cost'] = None
    result['cost_currency'] = destination
    return result


@router.get('/planning-references')
async def references(request: Request, action: Literal['create', 'update', 'planning'] = 'create', project_id: UUID | None = None, session=Session):
    from modules.module_currency.application.currency_service import CurrencyService
    code = 'pm.planning.manage' if action == 'planning' else permission('projects', action)
    require(request, code)
    currencies = await CurrencyService(session).repo.list_currencies()
    result = {'currencies': [{'id': c.code, 'name': c.name} for c in currencies], 'organizations': [], 'managers': []}
    if action == 'planning':
        result['owners'] = []
        if project_id:
            project = await PlanningService(session, request).project(project_id.hex, code)
            users = (await session.execute(text(
                'SELECT id,full_name AS name FROM users WHERE is_active=1 AND organization_id=:org ORDER BY full_name'),
                {'org':project['organization_id']})).mappings()
            result['owners'] = [dict(u) for u in users]
        return result
    scopes = request.state.permission_scopes.get(code, {'self'})
    users = (await session.execute(text('SELECT id,full_name,organization_id FROM users WHERE is_active=1 ORDER BY full_name'))).mappings()
    managers = [dict(u) for u in users if in_scope({'organization_id': u['organization_id'], 'project_manager_user_id': u['id']},
        request.state.user, request.state.is_admin, scopes)]
    result['managers'] = [
        {'id': u['id'], 'name': u['full_name'], 'organization_id': u['organization_id']}
        for u in managers
    ]
    orgs = {u['organization_id'] for u in managers}
    rows = (await session.execute(text('SELECT id,name FROM organizations WHERE is_active=1 ORDER BY name'))).mappings()
    result['organizations'] = [dict(r) for r in rows if r['id'] in orgs]
    return result


@router.get('/projects')
async def projects(request: Request, q: str = Query('', max_length=200),
                   skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100),
                   status: str | None = Query(None, max_length=100), session=Session):
    code = permission('projects', 'view')
    require(request, code)
    service = PlanningService(session, request)
    statuses = {value.strip() for value in status.split(',') if value.strip()} if status else set()
    rows = [r for r in await service.repo.rows('projects') if not r['deleted_at']
            and in_scope(r, request.state.user, request.state.is_admin, request.state.permission_scopes.get(code, {'self'}))
            and (not statuses or r['status'] in statuses)
            and (q.casefold() in r['project_code'].casefold() or q.casefold() in r['name'].casefold())]
    # The default page is the operational project inbox: return recently changed
    # projects first so pagination does not hide a project created in the current
    # workflow behind older, still-visible projects.
    rows.sort(key=lambda row: (row['updated_at'], row['created_at'], row['id']), reverse=True)
    return {'items': [await service.present('projects', r) for r in rows[skip:skip+limit]], 'total': len(rows)}


@router.post('/projects', status_code=201)
async def create_project(request: Request, payload: KINDS['projects'][1], session=Session):
    return await PlanningService(session, request).save('projects', None, payload)


@router.get('/projects/next-code')
async def next_project_code(request: Request, session=Session):
    require(request, 'pm.projects.create')
    codes = (await session.execute(text('SELECT project_code FROM pm_projects'))).scalars()
    highest = max(
        (int(match.group(1)) for code in codes if (match := re.fullmatch(r'P-(\d+)', code))),
        default=0,
    )
    return {'project_code': f'P-{highest + 1:03d}'}


@router.get('/projects/{project_id}')
async def project(project_id: UUID, request: Request, session=Session):
    service = PlanningService(session, request)
    row = await service.entity('projects', project_id.hex, project_id.hex)
    return await service.present('projects', row)


@router.put('/projects/{project_id}')
async def update_project(project_id: UUID, request: Request, payload: KINDS['projects'][1], session=Session):
    return await PlanningService(session, request).save('projects', project_id.hex, payload, project_id.hex)


@router.delete('/projects/{project_id}')
async def delete_project(project_id: UUID, request: Request, session=Session):
    return await PlanningService(session, request).delete('projects', project_id.hex, project_id.hex)


def child_routes(kind):
    model = KINDS[kind][1]
    path = '/projects/{project_id}/' + kind

    async def listing(project_id: UUID, request: Request, q: str = Query('', max_length=200),
                      parent_id: UUID | None = None, skip: int = Query(0, ge=0),
                      limit: int = Query(50, ge=1, le=100), session=Session):
        service = PlanningService(session, request)
        await service.project(project_id.hex, permission(kind, 'view'))
        rows = [r for r in await service.repo.rows(kind, project_id.hex) if not r['deleted_at']
                and (parent_id is None or r[KINDS[kind][4]] == parent_id.hex)
                and (q.casefold() in r[KINDS[kind][2]].casefold() or q.casefold() in r['name'].casefold())]
        return {'items': [await service.present(kind, r) for r in rows[skip:skip+limit]], 'total': len(rows)}

    async def create(project_id: UUID, request: Request, payload: model, session=Session):
        return await PlanningService(session, request).save(kind, project_id.hex, payload)

    async def detail(project_id: UUID, entity_id: UUID, request: Request, session=Session):
        service = PlanningService(session, request)
        return await service.present(kind, await service.entity(kind, project_id.hex, entity_id.hex))

    async def update(project_id: UUID, entity_id: UUID, request: Request, payload: model, session=Session):
        return await PlanningService(session, request).save(kind, project_id.hex, payload, entity_id.hex)

    async def delete(project_id: UUID, entity_id: UUID, request: Request, session=Session):
        return await PlanningService(session, request).delete(kind, project_id.hex, entity_id.hex)

    for suffix, method, endpoint in [('', 'GET', listing), ('', 'POST', create),
                                    ('/{entity_id}', 'GET', detail), ('/{entity_id}', 'PUT', update),
                                    ('/{entity_id}', 'DELETE', delete)]:
        router.add_api_route(path + suffix, endpoint, methods=[method], name=f'pm_{kind}_{endpoint.__name__}',
                             status_code=201 if method == 'POST' else 200)


for kind in ('phases', 'tasks', 'activities', 'requirements'):
    child_routes(kind)
