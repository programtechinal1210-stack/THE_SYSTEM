from datetime import date
from typing import Literal
from uuid import UUID
from pydantic import BaseModel,ConfigDict,Field
from fastapi import APIRouter,Depends,Request
from infrastructure.database.db_context import get_session
from ..domain.planning import Code,Name
from ..application.planning_copy import PlanningCopy

class CopyCommand(BaseModel):
    model_config=ConfigDict(extra='forbid')
    kind:Literal['phases','tasks','activities']
    source_id:UUID
    parent_id:UUID
    new_code:Code
    new_name:Name
    rate_date:date
    preview_token:str=Field(default='',max_length=64)

router=APIRouter(prefix='/api/v1/pm/projects',tags=['PM planning copy'])
Session=Depends(get_session,scope='function')

@router.post('/{project_id}/copy/preview')
async def preview(project_id:UUID,payload:CopyCommand,request:Request,session=Session):
    result=await PlanningCopy(session,request).preview(project_id.hex,payload)
    return {k:v for k,v in result.items() if k not in ('nodes','target')}

@router.post('/{project_id}/copy/apply',status_code=201)
async def apply(project_id:UUID,payload:CopyCommand,request:Request,session=Session):
    return await PlanningCopy(session,request).apply(project_id.hex,payload)
