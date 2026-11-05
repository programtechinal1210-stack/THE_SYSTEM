from uuid import UUID

from fastapi import APIRouter, Depends, Request

from infrastructure.database.db_context import get_session
from ..domain.baseline import DependencyInput
from ..application.baseline_service import BaselineService

router = APIRouter(prefix='/api/v1/pm', tags=['PM baseline'])
Session = Depends(get_session, scope='function')


@router.get('/projects/{project_id}/baselines')
async def baselines(project_id: UUID, request: Request, session=Session):
    return await BaselineService(session, request).list_baselines(project_id.hex)


@router.post('/projects/{project_id}/baselines', status_code=201)
async def approve(project_id: UUID, request: Request, session=Session):
    return await BaselineService(session, request).approve(project_id.hex)


@router.get('/projects/{project_id}/baselines/{baseline_id}')
async def baseline(project_id: UUID, baseline_id: UUID, request: Request, session=Session):
    return await BaselineService(session, request).baseline(project_id.hex, baseline_id.hex)


@router.get('/projects/{project_id}/dependencies')
async def dependencies(project_id: UUID, request: Request, session=Session):
    return await BaselineService(session, request).list_dependencies(project_id.hex)


@router.post('/projects/{project_id}/dependencies', status_code=201)
async def add_dependency(project_id: UUID, request: Request, payload: DependencyInput, session=Session):
    return await BaselineService(session, request).add_dependency(project_id.hex, payload)


@router.delete('/projects/{project_id}/dependencies/{dependency_id}')
async def remove_dependency(project_id: UUID, dependency_id: UUID, request: Request, session=Session):
    return await BaselineService(session, request).remove_dependency(project_id.hex, dependency_id.hex)
