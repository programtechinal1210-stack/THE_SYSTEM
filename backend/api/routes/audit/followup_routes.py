from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime

from infrastructure.database.db_context import get_session
from api.dependencies import get_current_user
from modules.module_users.domain.entities.user import User
from infrastructure.audit.models.followup_model import FollowUpModel
from infrastructure.audit.services.followup_service import FollowupService
from shared.shared_audit.dtos.followup_dto import (
    CreateFollowupDTO,
    UpdateFollowupDTO,
    FollowupResponseDTO,
)

router = APIRouter(prefix="/followups", tags=["audit-followups"])


def get_svc(s: AsyncSession = Depends(get_session, scope="function")):
    return FollowupService(s)


@router.post("", response_model=FollowupResponseDTO, status_code=201)
async def create_followup(
    data: CreateFollowupDTO,
    u: User = Depends(get_current_user),
    svc=Depends(get_svc),
):
    return await svc.create(u.id, data)


@router.get("", response_model=List[FollowupResponseDTO])
async def list_all_followups(
    skip: int = 0,
    limit: int = 20,
    svc=Depends(get_svc),
):
    from sqlalchemy import select

    result = await svc.session.execute(
        select(FollowUpModel)
        .offset(skip)
        .limit(limit)
        .order_by(FollowUpModel.created_at.desc())
    )
    return [
        FollowupResponseDTO.model_validate(m)
        for m in result.scalars().all()
    ]


@router.get(
    "/entity/{entity_type}/{entity_id}",
    response_model=List[FollowupResponseDTO],
)
async def list_entity_followups(
    entity_type: str,
    entity_id: UUID,
    svc=Depends(get_svc),
):
    return await svc.get_by_entity(entity_type, entity_id)


@router.get("/{followup_id}", response_model=FollowupResponseDTO)
async def get_followup(
    followup_id: UUID,
    svc=Depends(get_svc),
):
    item = await svc.get_by_id(followup_id)
    if not item:
        raise HTTPException(404, "غير موجود")
    return item


@router.put("/{followup_id}", response_model=FollowupResponseDTO)
async def update_followup(
    followup_id: UUID,
    data: UpdateFollowupDTO,
    svc=Depends(get_svc),
):
    item = await svc.update(followup_id, data)
    if not item:
        raise HTTPException(404, "غير موجود")
    return item


@router.delete("/{followup_id}", status_code=204)
async def delete_followup(
    followup_id: UUID,
    svc=Depends(get_svc),
):
    if not await svc.delete(followup_id):
        raise HTTPException(404, "غير موجود")