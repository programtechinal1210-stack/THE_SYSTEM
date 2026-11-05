from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict
from uuid import UUID
from infrastructure.database.db_context import get_session
from core import work_context

router = APIRouter(prefix='/api/v1/profile/work-context', tags=['Work context'])


class Selection(BaseModel):
    model_config = ConfigDict(extra='forbid')
    organization_id: UUID


@router.get('')
async def current(request: Request, session=Depends(get_session, scope='function')):
    return await work_context.context(session, request)


@router.put('')
async def choose(data: Selection, request: Request, session=Depends(get_session, scope='function')):
    return await work_context.select(session, request, data.organization_id)
