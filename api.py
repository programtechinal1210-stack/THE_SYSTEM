from uuid import UUID
from fastapi import APIRouter, Depends, Request, Query
from infrastructure.database.db_context import get_session
from .domain import (DailyWorkInput, ProgressInput, BlockerInput, ResolveInput, StatusInput, ReadinessInput,
                     PlanCreateInput, PlanItemInput, EstimateInput, ActualUpdateInput, PlanCloseInput,
                     PlanReopenInput, EvidenceInput, AssignmentInput)
from .application import DailyWorkService
from .planning_engine import DailyPlanningEngine

router = APIRouter(prefix='/api/v1/daily-work', tags=['Daily Work'])
Session = Depends(get_session, scope='function')

@router.get('/projects/{project_id}/items')
async def list_items(project_id: UUID, request: Request, work_date: str = Query(...), session=Session):
    return await DailyWorkService(session, request).list(project_id.hex, work_date)

@router.post('/projects/{project_id}/items', status_code=201)
async def create_item(project_id: UUID, request: Request, payload: DailyWorkInput, session=Session):
    return await DailyWorkService(session, request).create(project_id.hex, payload)

@router.post('/projects/{project_id}/items/{item_id}/status')
async def status(project_id: UUID, item_id: UUID, request: Request, payload: StatusInput, session=Session):
    return await DailyWorkService(session, request).transition(project_id.hex, item_id.hex, payload.status)

@router.post('/projects/{project_id}/items/{item_id}/readiness')
async def readiness(project_id: UUID, item_id: UUID, request: Request, payload: ReadinessInput, session=Session):
    return await DailyWorkService(session, request).check_readiness(project_id.hex, item_id.hex, payload)

@router.post('/projects/{project_id}/items/{item_id}/progress')
async def progress(project_id: UUID, item_id: UUID, request: Request, payload: ProgressInput, session=Session):
    return await DailyWorkService(session, request).record_progress(project_id.hex, item_id.hex, payload)

@router.post('/projects/{project_id}/items/{item_id}/blockers', status_code=201)
async def blocker(project_id: UUID, item_id: UUID, request: Request, payload: BlockerInput, session=Session):
    return await DailyWorkService(session, request).add_blocker(project_id.hex, item_id.hex, payload)

@router.post('/projects/{project_id}/items/{item_id}/blockers/{blocker_id}/resolve')
async def resolve(project_id: UUID, item_id: UUID, blocker_id: UUID, request: Request, payload: ResolveInput, session=Session):
    return await DailyWorkService(session, request).resolve_blocker(project_id.hex, item_id.hex, blocker_id.hex, payload)

@router.post('/projects/{project_id}/plans', status_code=201)
async def create_plan(project_id: UUID, request: Request, payload: PlanCreateInput, session=Session):
    return await DailyPlanningEngine(session, request).create_plan(project_id.hex, payload)

@router.get('/projects/{project_id}/plans')
async def list_plans(project_id: UUID, request: Request, plan_date: str | None = Query(None), session=Session):
    return await DailyPlanningEngine(session, request).plans(project_id.hex, plan_date)

@router.post('/projects/{project_id}/plans/{plan_id}/items', status_code=201)
async def add_plan_item(project_id: UUID, plan_id: UUID, request: Request, payload: PlanItemInput, session=Session):
    return await DailyPlanningEngine(session, request).add_item(project_id.hex, plan_id.hex, payload)

@router.post('/projects/{project_id}/plans/{plan_id}/commit')
async def commit_plan(project_id: UUID, plan_id: UUID, request: Request, session=Session):
    return await DailyPlanningEngine(session, request).commit(project_id.hex, plan_id.hex)

@router.post('/projects/{project_id}/plans/{plan_id}/close')
async def close_plan(project_id: UUID, plan_id: UUID, request: Request, payload: PlanCloseInput, session=Session):
    return await DailyPlanningEngine(session, request).close(project_id.hex, plan_id.hex, payload)

@router.post('/projects/{project_id}/plans/{plan_id}/reopen')
async def reopen_plan(project_id: UUID, plan_id: UUID, request: Request, payload: PlanReopenInput, session=Session):
    return await DailyPlanningEngine(session, request).reopen(project_id.hex, plan_id.hex, payload)

@router.post('/projects/{project_id}/items/{item_id}/estimates', status_code=201)
async def add_estimate(project_id: UUID, item_id: UUID, request: Request, payload: EstimateInput, session=Session):
    return await DailyPlanningEngine(session, request).add_estimate(project_id.hex, item_id.hex, payload)

@router.post('/projects/{project_id}/items/{item_id}/updates')
async def actual_update(project_id: UUID, item_id: UUID, request: Request, payload: ActualUpdateInput, session=Session):
    return await DailyPlanningEngine(session, request).record_actual(project_id.hex, item_id.hex, payload)

@router.post('/projects/{project_id}/items/{item_id}/evidence', status_code=201)
async def evidence(project_id: UUID, item_id: UUID, request: Request, payload: EvidenceInput, session=Session):
    return await DailyPlanningEngine(session, request).add_evidence(project_id.hex, item_id.hex, payload)

@router.get('/projects/{project_id}/items/{item_id}/metrics')
async def metrics(project_id: UUID, item_id: UUID, request: Request, session=Session):
    return await DailyPlanningEngine(session, request).metrics(project_id.hex, item_id.hex)

@router.get('/projects/{project_id}/plans/{plan_id}/control')
async def plan_control(project_id: UUID, plan_id: UUID, request: Request, session=Session):
    return await DailyPlanningEngine(session, request).plan_control(project_id.hex, plan_id.hex)

@router.get('/projects/{project_id}/items/{item_id}/assignments')
async def assignments(project_id: UUID, item_id: UUID, request: Request, session=Session):
    return await DailyPlanningEngine(session, request).assignments(project_id.hex, item_id.hex)

@router.post('/projects/{project_id}/items/{item_id}/assignments', status_code=201)
async def add_assignment(project_id: UUID, item_id: UUID, request: Request, payload: AssignmentInput, session=Session):
    return await DailyPlanningEngine(session, request).add_assignment(project_id.hex, item_id.hex, payload)
