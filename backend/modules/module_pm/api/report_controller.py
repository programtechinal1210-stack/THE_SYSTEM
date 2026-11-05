from uuid import UUID
from datetime import date
from typing import Literal
from pydantic import ValidationError

from fastapi import APIRouter, Depends, Request, HTTPException, Query

from infrastructure.database.db_context import get_session
from ..application.report_service import ReportService
from ..domain.reporting import ReportFilters

router = APIRouter(prefix='/api/v1/pm', tags=['PM reports'])
Session = Depends(get_session, scope='function')


def report_filters(date_from:date|None=None,date_to:date|None=None,phase_id:UUID|None=None,
                   task_id:UUID|None=None,activity_id:UUID|None=None,
                   status:Literal['issued','in_progress','completed','closed','rejected']|None=None):
    try:
        return ReportFilters(date_from=date_from,date_to=date_to,phase_id=phase_id,task_id=task_id,activity_id=activity_id,status=status)
    except ValidationError:
        raise HTTPException(422,'Invalid report filter date range') from None


Filters=Depends(report_filters)


@router.get('/reporting/portfolio')
async def portfolio(request:Request,status:str|None=Query(None,max_length=40),session=Session):
    return await ReportService(session,request).portfolio(status)


@router.get('/projects/{project_id}/command-center')
async def command_center(project_id: UUID, request: Request, session=Session,filters=Filters):
    return await ReportService(session, request).command_center(project_id.hex,filters)


@router.get('/projects/{project_id}/reporting/cost')
async def cost(project_id: UUID, request: Request, session=Session,filters=Filters):
    return await ReportService(session, request).cost_report(project_id.hex,filters)


@router.get('/projects/{project_id}/reporting/progress')
async def progress(project_id: UUID, request: Request, session=Session,filters=Filters):
    return await ReportService(session, request).progress_report(project_id.hex,filters)


@router.get('/projects/{project_id}/reporting/export')
async def export(project_id: UUID, request: Request, session=Session,filters=Filters,
                 risk_status:Literal['active','closed']|None=Query(None),
                 severity:Literal['high','medium','low']|None=Query(None),
                 q:str|None=Query(None,max_length=200)):
    request.state.audit_export = True
    request.state.audit_details = {'entity_type': 'pm.projects', 'entity_id': str(project_id),
                                   'summary': 'PM report export'}
    return await ReportService(session, request).export(
        project_id.hex,filters,risk_status=risk_status,severity=severity,query=q)


@router.get('/projects/{project_id}/reporting/{report_name}')
async def supporting_report(project_id:UUID,report_name:str,request:Request,session=Session,filters=Filters,
                            risk_status:Literal['active','closed']|None=Query(None),
                            severity:Literal['high','medium','low']|None=Query(None),
                            q:str|None=Query(None,max_length=200)):
    return await ReportService(session,request).supporting_report(
        project_id.hex,report_name,filters,
        risk_status=risk_status if report_name=='risk' else None,
        severity=severity if report_name=='risk' else None,
        query=q if report_name=='risk' else None)
