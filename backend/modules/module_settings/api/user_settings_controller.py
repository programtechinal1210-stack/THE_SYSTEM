from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from typing import List
from pydantic import BaseModel
from infrastructure.database.db_context import get_session
from api.dependencies import get_current_user
from modules.module_users.domain.entities.user import User
from ..domain.entities.user_setting import UserSetting
from ..infrastructure.models.user_setting_model import UserSettingModel
from ..infrastructure.repositories.base_setting_repository import BaseSettingRepository
from ..infrastructure.models.system_setting_model import SystemSettingModel
from ..application.settings_policy import USER_SETTINGS

router = APIRouter(tags=["user-settings"])

class UserSettingDTO(BaseModel):
    id: UUID
    setting_key: str
    value: object
    class Config: from_attributes = True

class UpdateUserSettingDTO(BaseModel):
    value: object

def repo(s: AsyncSession = Depends(get_session, scope="function")):
    return BaseSettingRepository(s, UserSettingModel, UserSetting)

@router.get("", response_model=List[UserSettingDTO])
async def my_settings(u: User = Depends(get_current_user), r = Depends(repo)):
    res = await r.session.execute(select(UserSettingModel).where(UserSettingModel.user_id == u.id))
    return [UserSettingDTO.model_validate(r._to_entity(m)) for m in res.scalars().all()]


@router.get("/effective")
async def effective_settings(request: Request, u: User = Depends(get_current_user), r=Depends(repo)):
    from ..application.center_service import state
    rows, _ = await state(r.session, 'user', u.id.hex, u.organization_id, include_inherited=True)
    exposed={'core.theme','core.ude.palette','core.font_size','core.language','core.density','core.timezone','core.date_format','core.notifications.sound','core.notifications.quiet'}
    from core.work_context import context
    return [{'setting_key':row['key'].removeprefix('core.'),'value':row['value'],'source':row['source'],'locked':row['locked']} for row in rows if row['key'] in exposed] + [
        {'setting_key': 'current_organization', 'value': await context(r.session, request), 'source': 'context', 'locked': False}]
@router.put("/{key}", response_model=UserSettingDTO)
async def update_my_setting(key: str, data: UpdateUserSettingDTO, u: User = Depends(get_current_user), r = Depends(repo)):
    from ..application.settings_policy import validate_user_setting
    validate_user_setting(key, data.value)
    from sqlalchemy import text
    await r.session.execute(text("DELETE FROM setting_overrides WHERE scope_type='user' AND scope_id=:id AND setting_key=:key"),{'id':u.id.hex,'key':'core.'+key})
    definition = await r.session.scalar(select(SystemSettingModel).where(SystemSettingModel.key == "core." + key))
    if definition and definition.is_active and (definition.validation_rules or {}).get("user_override") is False:
        raise HTTPException(403, "This setting is locked by the institution")
    res = await r.session.execute(select(UserSettingModel).where(UserSettingModel.user_id == u.id, UserSettingModel.setting_key == key))
    m = res.scalar_one_or_none()
    if m:
        entity = r._to_entity(m)
        return UserSettingDTO.model_validate(await r.save(entity.model_copy(update={"value": data.value})))
    else:
        entity = UserSetting(user_id=u.id, setting_key=key, value=data.value)
        return UserSettingDTO.model_validate(await r.save(entity))


@router.delete("/{key}", status_code=204)
async def reset_my_setting(key: str, u: User = Depends(get_current_user), r=Depends(repo)):
    from sqlalchemy import text
    await r.session.execute(text("DELETE FROM setting_overrides WHERE scope_type='user' AND scope_id=:id AND setting_key=:key"),{'id':u.id.hex,'key':'core.'+key})
    from sqlalchemy import delete
    if key not in USER_SETTINGS:
        raise HTTPException(403, "Unknown personal setting")
    await r.session.execute(delete(UserSettingModel).where(UserSettingModel.user_id == u.id, UserSettingModel.setting_key == key))


