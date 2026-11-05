from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request

from infrastructure.database.db_context import get_session
from ..domain.wep import Carryover, StatusChange, WeeklyPlan, WeeklyPlanItem, WeeklyCommitmentUpdate
from ..application.wep_service import WepService

router = APIRouter(prefix='/api/v1/pm', tags=['PM WEP'])
Session = Depends(get_session, scope='function')


@router.get('/projects/{project_id}/weekly-plans')
async def list_plans(project_id: UUID, request: Request, session=Session):
    return await WepService(session, request).list_plans(project_id.hex)


@router.post('/projects/{project_id}/weekly-plans', status_code=201)
async def create_plan(project_id: UUID, request: Request, payload: WeeklyPlan, session=Session):
    return await WepService(session, request).create_plan(project_id.hex, payload)


@router.get('/projects/{project_id}/weekly-plans/{plan_id}')
async def detail_plan(project_id: UUID, plan_id: UUID, request: Request, session=Session):
    return await WepService(session, request).detail_plan(project_id.hex, plan_id.hex)


@router.get('/projects/{project_id}/daily-work-candidates')
async def daily_work_candidates(project_id: UUID, request: Request,
                                business_date: date = Query(...), session=Session):
    return await WepService(session, request).daily_work_candidates(
        project_id.hex, business_date.isoformat())


@router.post('/projects/{project_id}/weekly-plans/{plan_id}/status')
async def transition(project_id: UUID, plan_id: UUID, request: Request, payload: StatusChange, session=Session):
    return await WepService(session, request).transition(project_id.hex, plan_id.hex, payload.status, payload.reason)


@router.post('/projects/{project_id}/weekly-plans/{plan_id}/items', status_code=201)
async def add_item(project_id: UUID, plan_id: UUID, request: Request, payload: WeeklyPlanItem, session=Session):
    return await WepService(session, request).add_item(project_id.hex, plan_id.hex, payload)


@router.put('/projects/{project_id}/weekly-plans/{plan_id}/items/{item_id}')
async def update_item(project_id: UUID, plan_id: UUID, item_id: UUID, request: Request,
                      payload: WeeklyCommitmentUpdate, session=Session):
    return await WepService(session, request).update_item(project_id.hex, plan_id.hex, item_id.hex, payload)


@router.get('/projects/{project_id}/weekly-plans/{plan_id}/baselines')
async def baselines(project_id: UUID, plan_id: UUID, request: Request, session=Session):
    return await WepService(session, request).baselines(project_id.hex, plan_id.hex)


@router.post('/projects/{project_id}/weekly-plans/{plan_id}/close')
async def close_week(project_id: UUID, plan_id: UUID, request: Request, session=Session):
    return await WepService(session, request).close_week(project_id.hex, plan_id.hex)


@router.post('/projects/{project_id}/weekly-plans/{plan_id}/carryover')
async def carryover(project_id: UUID, plan_id: UUID, request: Request, payload: Carryover, session=Session):
    return await WepService(session, request).carryover(project_id.hex, plan_id.hex, payload)
