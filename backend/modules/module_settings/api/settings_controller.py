from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from typing import List
from pydantic import BaseModel
from datetime import datetime

from infrastructure.database.db_context import get_session
from api.dependencies import get_current_user
from modules.module_users.domain.entities.user import User
from ..domain.entities.setting_category import SettingCategory
from ..domain.entities.system_setting import SystemSetting
from ..infrastructure.models.setting_category_model import SettingCategoryModel
from ..infrastructure.models.system_setting_model import SystemSettingModel
from ..infrastructure.repositories.base_setting_repository import BaseSettingRepository

router = APIRouter(tags=["settings"])

class CategoryDTO(BaseModel):
    id: UUID
    code: str
    name_ar: str
    name_en: str
    is_active: bool
    class Config: from_attributes = True

class SettingDTO(BaseModel):
    id: UUID
    key: str
    value: object
    data_type: str
    description_ar: str | None = None
    is_active: bool
    validation_rules: dict | None = None
    class Config: from_attributes = True

class UpdateSettingDTO(BaseModel):
    value: object | None = None
    is_active: bool | None = None
    allow_user_override: bool | None = None

def cat_repo(s: AsyncSession = Depends(get_session, scope="function")):
    return BaseSettingRepository(s, SettingCategoryModel, SettingCategory)

def set_repo(s: AsyncSession = Depends(get_session, scope="function")):
    return BaseSettingRepository(s, SystemSettingModel, SystemSetting)

@router.get("/categories", response_model=List[CategoryDTO])
async def list_categories(repo = Depends(cat_repo)):
    return [CategoryDTO.model_validate(c) for c in await repo.all()]

@router.get("", response_model=List[SettingDTO])
async def list_settings(repo = Depends(set_repo)):
    return [SettingDTO.model_validate(s) for s in await repo.all() if not s.is_encrypted]

@router.get("/by-key/{key}", response_model=SettingDTO)
async def get_setting(key: str, repo = Depends(set_repo)):
    # البحث في جميع الإعدادات
    all_settings = await repo.all()
    for s in all_settings:
        if s.key == key and not s.is_encrypted:
            return SettingDTO.model_validate(s)
    raise HTTPException(404, "الإعداد غير موجود")

@router.put("/by-key/{key}", response_model=SettingDTO)
async def update_setting(key: str, data: UpdateSettingDTO, request: Request, u: User = Depends(get_current_user), repo = Depends(set_repo)):
    if key.startswith('core.module_enabled.') or key in ('core.logo', 'core.default_organization'):
        raise HTTPException(409,'استخدم العملية المخصصة في مركز الإعدادات')
    from ..application.center_catalog import catalog, validate
    from core.access import require
    definition = catalog().get(key)
    if definition:
        require(request, definition['permission'])
        if not request.state.is_admin and 'institution' not in request.state.permission_scopes.get(definition['permission'],set()):
            raise HTTPException(403, 'تعديل إعدادات النظام يتطلب نطاق المؤسسة')
        if definition['sensitive']:
            raise HTTPException(409, 'استخدم مركز الإعدادات لمراجعة أثر هذا التغيير')
        if 'value' in data.model_fields_set: validate(definition, data.value)
    r = await repo.session.execute(select(SystemSettingModel).where(SystemSettingModel.key == key))
    m = r.scalar_one_or_none()
    if not m:
        raise HTTPException(404, "الإعداد غير موجود")
    if m.is_encrypted:
        raise HTTPException(403, "Secret settings require dedicated secret storage")
    from ..application.settings_policy import validate_value
    if "value" in data.model_fields_set:
        validate_value(m.data_type, data.value, m.options, m.validation_rules)
        from ..application.settings_policy import USER_SETTINGS, validate_user_setting
        if key.removeprefix("core.") in USER_SETTINGS:
            validate_user_setting(key.removeprefix("core."), data.value)
    entity = repo._to_entity(m)
    upd = data.model_dump(exclude_none=True)
    if "allow_user_override" in upd:
        upd["validation_rules"] = {**(m.validation_rules or {}), "user_override": upd.pop("allow_user_override")}
    request.state.audit_details = {"old": {"value": m.value, "is_active": m.is_active, "validation_rules": m.validation_rules},
                                   "new": upd, "entity_type": "system_setting", "entity_id": str(m.id)}
    if "value" in upd:
        upd["updated_by"] = u.id
    return SettingDTO.model_validate(await repo.save(entity.model_copy(update=upd)))


@router.post("/by-key/{key}/reset", response_model=SettingDTO)
async def reset_setting(key: str, request: Request, u: User = Depends(get_current_user), repo=Depends(set_repo)):
    if key.startswith('core.module_enabled.') or key in ('core.logo', 'core.default_organization'):
        raise HTTPException(409,'استخدم العملية المخصصة في مركز الإعدادات')
    from ..application.center_catalog import catalog
    from core.access import require
    definition = catalog().get(key)
    if definition:
        require(request, definition['permission'])
        if not request.state.is_admin and 'institution' not in request.state.permission_scopes.get(definition['permission'],set()):
            raise HTTPException(403, 'تعديل إعدادات النظام يتطلب نطاق المؤسسة')
        if definition['sensitive']: raise HTTPException(409, 'استخدم مركز الإعدادات لمراجعة أثر إعادة الضبط')
    model = await repo.session.scalar(select(SystemSettingModel).where(SystemSettingModel.key == key))
    if not model:
        raise HTTPException(404, "Setting not found")
    if model.is_encrypted:
        raise HTTPException(403, "Secret settings require dedicated storage")
    request.state.audit_details = {"old": {"value": model.value},
                                   "new": {"value": model.default_value},
                                   "entity_type": "system_setting", "entity_id": str(model.id)}
    model.value = model.default_value
    model.updated_by = u.id
    await repo.session.flush()
    return SettingDTO.model_validate(model)


