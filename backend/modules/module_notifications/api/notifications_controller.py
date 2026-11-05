from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import List
from pydantic import BaseModel
from datetime import datetime
from infrastructure.database.db_context import get_session
from api.dependencies import get_current_user
from modules.module_users.domain.entities.user import User
from ..domain.entities.notification import Notification
from ..domain.entities.notification_channel import NotificationChannel
from ..infrastructure.models.notification_model import NotificationModel
from ..infrastructure.models.notification_channel_model import NotificationChannelModel
from ..infrastructure.repositories.base_notification_repository import BaseNotificationRepository

router = APIRouter(tags=["notifications"])

class NotifDTO(BaseModel):
    id: UUID
    type: str
    title: str
    content: str
    link: str | None = None
    is_read: bool
    created_at: datetime | None = None
    class Config: from_attributes = True

class ChannelDTO(BaseModel):
    id: UUID
    code: str
    name_ar: str
    name_en: str
    is_active: bool
    class Config: from_attributes = True

class MarkReadDTO(BaseModel):
    notification_ids: List[UUID]

class SendNotificationDTO(BaseModel):
    user_id: UUID
    type: str = "system_alert"
    title: str
    content: str
    link: str | None = None
    entity_type: str | None = None
    entity_id: UUID | None = None

def notif_repo(s: AsyncSession = Depends(get_session, scope="function")):
    return BaseNotificationRepository(s, NotificationModel, Notification)

def chan_repo(s: AsyncSession = Depends(get_session, scope="function")):
    return BaseNotificationRepository(s, NotificationChannelModel, NotificationChannel)

@router.get("", response_model=List[NotifDTO])
async def my_notifications(u: User = Depends(get_current_user), unread: bool = False, limit: int = Query(50, ge=1, le=100), skip: int = Query(0, ge=0), r = Depends(notif_repo)):
    items = await r.get_by_user(u.id, unread_only=unread, limit=limit, skip=skip)
    return [NotifDTO.model_validate(n) for n in items]

@router.get("/unread-count")
async def unread_count(u: User = Depends(get_current_user), r = Depends(notif_repo)):
    return {"count": await r.unread_count(u.id)}

@router.post("/send", response_model=NotifDTO, status_code=201)
async def send_notification(data: SendNotificationDTO, u: User = Depends(get_current_user), r = Depends(notif_repo)):
    notif = Notification(
        user_id=data.user_id,
        type=data.type,
        title=data.title,
        content=data.content,
        link=data.link,
        entity_type=data.entity_type,
        entity_id=data.entity_id
    )
    saved = await r.save(notif)
    return NotifDTO.model_validate(saved)

@router.put("/mark-read/{notification_id}")
async def mark_single_read(notification_id: UUID, u: User = Depends(get_current_user), r = Depends(notif_repo)):
    await r.mark_read([notification_id], u.id)
    return {"detail": "تم تحديد كمقروء"}

@router.put("/mark-read")
async def mark_read(data: MarkReadDTO, u: User = Depends(get_current_user), r = Depends(notif_repo)):
    await r.mark_read(data.notification_ids, u.id)
    return {"detail": "تم التحديث"}

@router.put("/mark-all-read")
async def mark_all_read(u: User = Depends(get_current_user), r = Depends(notif_repo)):
    await r.mark_all_read(u.id)
    return {"detail": "تم تحديث الكل"}

@router.get("/channels", response_model=List[ChannelDTO])
async def list_channels(r = Depends(chan_repo)):
    return [ChannelDTO.model_validate(c) for c in await r.all()]


@router.get("/{notification_id}", response_model=NotifDTO)
async def notification_detail(notification_id: UUID, request: Request, u: User = Depends(get_current_user), r=Depends(notif_repo)):
    from sqlalchemy import select
    item = await r.session.scalar(select(NotificationModel).where(
        NotificationModel.id == notification_id, NotificationModel.user_id == u.id))
    if item is None:
        raise HTTPException(404, "Notification not found")
    # Legacy stored links are not trusted as executable or external destinations.
    result = NotifDTO.model_validate(item)
    if item.entity_type and item.entity_id:
        from core.module_registry import registry
        try:
            reference = await registry.resolve_entity(item.entity_type, item.entity_id, request, r.session)
            result.link = reference["href"]
        except HTTPException as exc:
            if exc.status_code not in (403, 404):
                raise
            result.link = None
    if result.link and (not result.link.startswith("/") or result.link.startswith("//") or "\\" in result.link):
        result.link = None
    return result
