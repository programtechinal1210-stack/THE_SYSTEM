from uuid import UUID
from fastapi import APIRouter,Depends,Request
from infrastructure.database.db_context import get_session
from ..application.schedule_version_service import ScheduleVersionService
from ..application.forecast_execution_read_adapter import ForecastExecutionReadAdapter
from ..domain.schedule_version import ApproveScheduleVersion,CreateScheduleVersion,RecalculateForecast,RejectScheduleVersion
router=APIRouter(prefix='/api/v1/pm',tags=['PM schedules']); Session=Depends(get_session,scope='function')
@router.get('/projects/{project_id}/schedule-versions')
async def list_(project_id:UUID,request:Request,session=Session): return await ScheduleVersionService(session,request).list(project_id.hex)
@router.post('/projects/{project_id}/schedule-versions',status_code=201)
async def create(project_id:UUID,payload:CreateScheduleVersion,request:Request,session=Session): return await ScheduleVersionService(session,request).create(project_id.hex,payload)
@router.post('/projects/{project_id}/schedule-versions/recalculate-actual',status_code=201)
async def recalculate_actual(project_id:UUID,payload:RecalculateForecast,request:Request,session=Session): return await ScheduleVersionService(session,request).recalculate_actual(project_id.hex,payload)
@router.get('/projects/{project_id}/schedule-versions/{version_id}')
async def detail(project_id:UUID,version_id:UUID,request:Request,session=Session): return await ScheduleVersionService(session,request).detail(project_id.hex,version_id.hex)
@router.get('/projects/{project_id}/schedule-versions/{version_id}/execution-impact')
async def execution_impact(project_id:UUID,version_id:UUID,request:Request,session=Session): return await ForecastExecutionReadAdapter(session,request).read(project_id.hex,version_id.hex)
@router.post('/projects/{project_id}/schedule-versions/{version_id}/propose')
async def propose(project_id:UUID,version_id:UUID,request:Request,session=Session): return await ScheduleVersionService(session,request).propose(project_id.hex,version_id.hex)
@router.post('/projects/{project_id}/schedule-versions/{version_id}/approve')
async def approve(project_id:UUID,version_id:UUID,request:Request,payload:ApproveScheduleVersion|None=None,session=Session): return await ScheduleVersionService(session,request).approve(project_id.hex,version_id.hex,payload)
@router.post('/projects/{project_id}/schedule-versions/{version_id}/reject')
async def reject(project_id:UUID,version_id:UUID,payload:RejectScheduleVersion,request:Request,session=Session): return await ScheduleVersionService(session,request).reject(project_id.hex,version_id.hex,payload)
