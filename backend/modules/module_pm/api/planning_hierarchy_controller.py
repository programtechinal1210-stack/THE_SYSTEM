from typing import Literal
from uuid import UUID
from pydantic import BaseModel,ConfigDict,Field
from fastapi import APIRouter,Depends,Request
from infrastructure.database.db_context import get_session
from ..application.planning_hierarchy import PlanningHierarchy

class Command(BaseModel):
    model_config=ConfigDict(extra='forbid')
    kind: Literal['phases','tasks','activities']
    entity_id: UUID
    operation: Literal['up','down','before','after','move','promote']
    target_id: UUID | None=None
    new_code: str=Field(default='',max_length=80)
    new_name: str=Field(default='',max_length=200)
    preview_token: str=''

router=APIRouter(prefix='/api/v1/pm/projects',tags=['PM hierarchy'])
Session=Depends(get_session,scope='function')

@router.post('/{project_id}/hierarchy/preview')
async def preview(project_id:UUID,payload:Command,request:Request,session=Session):
    result=await PlanningHierarchy(session,request).inspect(project_id.hex,payload)
    return {k:v for k,v in result.items() if k not in ('row','siblings')}

@router.post('/{project_id}/hierarchy/apply')
async def apply(project_id:UUID,payload:Command,request:Request,session=Session):
    return await PlanningHierarchy(session,request).apply(project_id.hex,payload)
