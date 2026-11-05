from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from fastapi import APIRouter, Depends, Request
from infrastructure.database.db_context import get_session
from ..application.planning_workflow import PlanningWorkflow

router=APIRouter(prefix='/api/v1/pm/projects',tags=['PM planning approval'])
Session=Depends(get_session,scope='function')

class Decision(BaseModel):
    model_config=ConfigDict(extra='forbid')
    decision: Literal['pending','approved','rejected']
    reason: str=Field(default='',max_length=2000)

class Transition(BaseModel):
    model_config=ConfigDict(extra='forbid')
    status: Literal['planning','planned','in_progress']

@router.get('/{project_id}/approval')
async def overview(project_id:UUID,request:Request,session=Session):
    return await PlanningWorkflow(session,request).overview(project_id.hex)

@router.post('/{project_id}/approval/{activity_id}')
async def decision(project_id:UUID,activity_id:UUID,payload:Decision,request:Request,session=Session):
    return await PlanningWorkflow(session,request).decision(project_id.hex,activity_id.hex,payload.decision,payload.reason)

@router.post('/{project_id}/approve-all')
async def approve_all(project_id:UUID,request:Request,session=Session):
    return await PlanningWorkflow(session,request).approve_all(project_id.hex)

@router.post('/{project_id}/planning-status')
async def transition(project_id:UUID,payload:Transition,request:Request,session=Session):
    return await PlanningWorkflow(session,request).transition(project_id.hex,payload.status)
