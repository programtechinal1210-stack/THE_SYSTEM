from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from infrastructure.database.db_context import get_session
from ..domain.execution import (Consumption, QuantityUpdate, StatusChange, WorkOrder,
                                WorkOrderDecision, WorkOrderUpdate)
from ..application.execution_service import ExecutionService

router = APIRouter(prefix='/api/v1/pm', tags=['PM execution'])
Session = Depends(get_session, scope='function')


@router.get('/projects/{project_id}/execution-rate')
async def execution_rate(project_id: UUID, request: Request, source: str, rate_date: str,
                         quantity: str | None = None, unit_price: str | None = None, session=Session):
    return await ExecutionService(session, request).preview_consumption_cost(
        project_id.hex, source, rate_date, quantity, unit_price)


@router.get('/projects/{project_id}/work-orders')
async def list_wo(project_id: UUID, request: Request, activity_id: UUID | None = None, session=Session):
    return await ExecutionService(session, request).list_work_orders(
        project_id.hex, activity_id.hex if activity_id else None)


@router.post('/projects/{project_id}/work-orders', status_code=201)
async def create_wo(project_id: UUID, request: Request, payload: WorkOrder, session=Session):
    return await ExecutionService(session, request).create_work_order(project_id.hex, payload)


@router.get('/projects/{project_id}/work-orders/{wo_id}')
async def detail_wo(project_id: UUID, wo_id: UUID, request: Request, session=Session):
    return await ExecutionService(session, request).detail_work_order(project_id.hex, wo_id.hex)


@router.post('/projects/{project_id}/work-orders/{wo_id}/status')
async def transition(project_id: UUID, wo_id: UUID, request: Request, payload: StatusChange, session=Session):
    return await ExecutionService(session, request).transition(project_id.hex, wo_id.hex, payload.status)


@router.put('/projects/{project_id}/work-orders/{wo_id}')
async def update_wo(project_id: UUID, wo_id: UUID, request: Request, payload: WorkOrderUpdate, session=Session):
    return await ExecutionService(session, request).update_work_order(project_id.hex, wo_id.hex, payload)


@router.post('/projects/{project_id}/work-orders/{wo_id}/approve')
async def approve_wo(project_id: UUID, wo_id: UUID, request: Request, session=Session):
    return await ExecutionService(session, request).approve(project_id.hex, wo_id.hex)


@router.post('/projects/{project_id}/work-orders/{wo_id}/reject')
async def reject_wo(project_id: UUID, wo_id: UUID, request: Request, payload: WorkOrderDecision, session=Session):
    return await ExecutionService(session, request).reject(project_id.hex, wo_id.hex, payload.reason)


@router.post('/projects/{project_id}/work-orders/{wo_id}/partial-close')
async def partial_close_wo(project_id: UUID, wo_id: UUID, request: Request, payload: WorkOrderDecision, session=Session):
    return await ExecutionService(session, request).close_partially(project_id.hex, wo_id.hex, payload.reason)


@router.post('/projects/{project_id}/work-orders/{wo_id}/quantity')
async def quantity(project_id: UUID, wo_id: UUID, request: Request, payload: QuantityUpdate, session=Session):
    return await ExecutionService(session, request).record_quantity(
        project_id.hex, wo_id.hex, payload.quantity, payload.notes)


@router.get('/projects/{project_id}/work-orders/{wo_id}/events')
async def events(project_id: UUID, wo_id: UUID, request: Request, session=Session):
    return await ExecutionService(session, request).quantity_events(project_id.hex, wo_id.hex)


@router.get('/projects/{project_id}/work-orders/{wo_id}/consumptions')
async def list_cons(project_id: UUID, wo_id: UUID, request: Request, session=Session):
    return await ExecutionService(session, request).list_consumptions(project_id.hex, wo_id.hex)


@router.post('/projects/{project_id}/work-orders/{wo_id}/consumptions', status_code=201)
async def create_cons(project_id: UUID, wo_id: UUID, request: Request, payload: Consumption, session=Session):
    if payload.work_order_id != wo_id:
        raise HTTPException(422, 'work_order_id must match the URL')
    return await ExecutionService(session, request).create_consumption(project_id.hex, payload)
