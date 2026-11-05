from fastapi import APIRouter, Request, Depends
from infrastructure.database.db_context import get_session
from core.module_registry import registry

router = APIRouter()


@router.get("/api/v1/modules")
async def modules(request: Request, session=Depends(get_session,scope='function')):
    from modules.module_settings.application.module_policy import enabled_modules
    enabled=await enabled_modules(session)
    return [{"code": m.code, "name": m.name, "href": m.href, "version": m.version}
            for m in registry.visible(request.state.permissions, request.state.is_admin) if enabled[m.code]]
