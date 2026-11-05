from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from typing import List
from pydantic import BaseModel
from infrastructure.database.db_context import get_session
from api.dependencies import get_current_user
from modules.module_users.domain.entities.user import User
from ..domain.entities.user_notification_setting import UserNotificationSetting
from ..infrastructure.models.user_notification_setting_model import UserNotificationSettingModel
from ..infrastructure.repositories.base_setting_repository import BaseSettingRepository

router = APIRouter(tags=["notification-settings"])

class NotifSettingDTO(BaseModel):
    id: UUID
    notification_type: str
    channel: str
    is_enabled: bool
    class Config: from_attributes = True

class UpdateNotifSettingDTO(BaseModel):
    is_enabled: bool

def repo(s: AsyncSession = Depends(get_session, scope="function")):
    return BaseSettingRepository(s, UserNotificationSettingModel, UserNotificationSetting)

@router.get("", response_model=List[NotifSettingDTO])
async def my_notif_settings(u: User = Depends(get_current_user), r = Depends(repo)):
    res = await r.session.execute(select(UserNotificationSettingModel).where(UserNotificationSettingModel.user_id == u.id))
    return [NotifSettingDTO.model_validate(r._to_entity(m)) for m in res.scalars().all()]


@router.get("/available")
async def available(u: User = Depends(get_current_user), r=Depends(repo)):
    from modules.module_notifications.infrastructure.models.notification_template_model import NotificationTemplateModel
    templates = (await r.session.scalars(select(NotificationTemplateModel).where(
        NotificationTemplateModel.is_active.is_(True), NotificationTemplateModel.channel == "in_app"))).all()
    preferences = {p.notification_type: p.is_enabled for p in (await r.session.scalars(
        select(UserNotificationSettingModel).where(UserNotificationSettingModel.user_id == u.id,
                                                   UserNotificationSettingModel.channel == "in_app"))).all()}
    return [{"notification_type": template.type, "channel": "in_app", "is_enabled": preferences.get(template.type, True)} for template in templates]


@router.put("/by-type/{code}")
async def save_preference(code: str, data: UpdateNotifSettingDTO, u: User = Depends(get_current_user), r=Depends(repo)):
    from modules.module_notifications.infrastructure.models.notification_template_model import NotificationTemplateModel
    from sqlalchemy.dialects.sqlite import insert
    template = await r.session.scalar(select(NotificationTemplateModel).where(
        NotificationTemplateModel.type == code, NotificationTemplateModel.is_active.is_(True),
        NotificationTemplateModel.channel == "in_app"))
    if template is None:
        raise HTTPException(404, "Notification type unavailable")
    statement = insert(UserNotificationSettingModel).values(user_id=u.id, notification_type=code, channel="in_app", is_enabled=data.is_enabled)
    await r.session.execute(statement.on_conflict_do_update(index_elements=["user_id", "notification_type", "channel"], set_={"is_enabled": data.is_enabled}))
    return {"notification_type": code, "channel": "in_app", "is_enabled": data.is_enabled}

@router.put("/{setting_id}", response_model=NotifSettingDTO)
async def toggle_notif_setting(setting_id: UUID, data: UpdateNotifSettingDTO, u: User = Depends(get_current_user), r = Depends(repo)):
    entity = await r.get(setting_id)
    if not entity or entity.user_id != u.id:
        raise HTTPException(404, "غير موجود")
    return NotifSettingDTO.model_validate(await r.save(entity.model_copy(update={"is_enabled": data.is_enabled})))


