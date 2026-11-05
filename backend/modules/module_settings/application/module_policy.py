from sqlalchemy import select
from core.module_registry import registry
from ..infrastructure.models.system_setting_model import SystemSettingModel

PROTECTED={'users','organizations','entities','settings','notifications','audit'}

async def enabled_modules(session):
    values={r.key:r.value for r in (await session.scalars(select(SystemSettingModel).where(SystemSettingModel.key.like('core.module_enabled.%')))).all()}
    return {code:module.enabled and (code in PROTECTED or values.get('core.module_enabled.'+code,True) is True) for code,module in registry.modules.items()}
