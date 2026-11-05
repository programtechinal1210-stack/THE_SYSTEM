from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request

from infrastructure.database.db_context import get_session
from ..domain.control import CONTROL_KINDS, StatusChange
from ..application.control_service import ControlService

router = APIRouter(prefix='/api/v1/pm', tags=['PM control'])
Session = Depends(get_session, scope='function')


def routes(kind):
    model = CONTROL_KINDS[kind][1]
    path = '/projects/{project_id}/' + kind

    async def listing(project_id: UUID, request: Request, q: str = Query('', max_length=200), session=Session):
        return await ControlService(session, request).list(kind, project_id.hex, q)

    async def create(project_id: UUID, request: Request, payload: model, session=Session):
        return await ControlService(session, request).save(kind, project_id.hex, payload)

    async def detail(project_id: UUID, entity_id: UUID, request: Request, session=Session):
        return await ControlService(session, request).detail(kind, project_id.hex, entity_id.hex)

    async def update(project_id: UUID, entity_id: UUID, request: Request, payload: model, session=Session):
        return await ControlService(session, request).save(kind, project_id.hex, payload, entity_id.hex)

    async def delete(project_id: UUID, entity_id: UUID, request: Request, session=Session):
        return await ControlService(session, request).delete(kind, project_id.hex, entity_id.hex)

    async def status(project_id: UUID, entity_id: UUID, request: Request, payload: StatusChange, session=Session):
        return await ControlService(session, request).set_status(kind, project_id.hex, entity_id.hex, payload.status)

    for suffix, method, endpoint in [('', 'GET', listing), ('', 'POST', create),
                                     ('/{entity_id}', 'GET', detail), ('/{entity_id}', 'PUT', update),
                                     ('/{entity_id}', 'DELETE', delete), ('/{entity_id}/status', 'POST', status)]:
        router.add_api_route(path + suffix, endpoint, methods=[method], name=f'pm_{kind}_{endpoint.__name__}',
                             status_code=201 if endpoint is create else 200)


for kind in CONTROL_KINDS:
    routes(kind)
