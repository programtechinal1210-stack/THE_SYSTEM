from uuid import UUID
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from core import legal_entities as service
from infrastructure.database.db_context import get_session

router = APIRouter(prefix='/api/v1/legal-entities', tags=['Legal reference configuration'])
Session = Depends(get_session, scope='function')


class EntityInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    valuation_currency: str | None = Field(default=None, min_length=1, max_length=10)


class OrgLink(BaseModel):
    model_config = ConfigDict(extra='forbid')
    organization_id: UUID


@router.get('')
async def listing(request: Request, session=Session):
    return await service.listing(session, request)


@router.post('', status_code=201)
async def create(data: EntityInput, request: Request, session=Session):
    return await service.create(session, request, data)


@router.put('/{identifier}')
async def update(identifier: UUID, data: EntityInput, request: Request, session=Session):
    return await service.update(session, request, identifier, data)


@router.post('/{identifier}/approve')
async def approve(identifier: UUID, request: Request, session=Session):
    return await service.approve(session, request, identifier)


@router.post('/{identifier}/organizations')
async def link(identifier: UUID, data: OrgLink, request: Request, session=Session):
    return await service.link(session, request, identifier, data.organization_id)
