# api/main.py
# api/main.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))  # backend/


from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging

from infrastructure.audit.middleware.audit_middleware import AuditMiddleware
from api.middleware.auth import AuthMiddleware
from api.middleware.logging import LoggingMiddleware
from api.middleware.error_handler import ErrorHandlerMiddleware
from api.routes.router import router
from core.config import settings
from infrastructure.database.db_context import init_db, close_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from infrastructure.database.process_lock import acquire
    lease = acquire(settings.DATABASE_URL)
    app.state.database_lease = lease
    await init_db()
    from core.module_registry import registry
    from infrastructure.database.db_context import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        await registry.install_definitions(session)
        await session.commit()
    try:
        from sqlalchemy.engine import make_url as _make_url
        _db_file = _make_url(settings.DATABASE_URL).database or ""
        if ".work" not in _db_file.replace("\\", "/"):
            from sqlalchemy import text as _text
            async with AsyncSessionLocal() as _s:
                await _s.execute(_text("UPDATE user_sessions SET is_active=0, logout_time=CURRENT_TIMESTAMP WHERE is_active=1"))
                await _s.commit()
            logger.info("All sessions revoked on startup")
    except Exception as exc:
        logger.warning("Startup revocation skipped: %s", exc)
    try:
        yield
    finally:
        await close_db()
        if lease: lease.close()


app = FastAPI(
    title="THE_SYSTEM Core",
    description="النواة المؤسسية المشتركة",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# ══════════════════════════════════════
# DEBUG: تفاصيل 422
# ══════════════════════════════════════
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    logger.info("Request validation failed: %s", request.url.path)
    return JSONResponse(
        status_code=422,
        content={"detail": [{"loc": e["loc"], "msg": e["msg"], "type": e["type"]} for e in exc.errors()]}
    )

# ══════════════════════════════════════
# Middleware
# ══════════════════════════════════════
app.add_middleware(CORSMiddleware, allow_origins=settings.CORS_ORIGINS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.add_middleware(ErrorHandlerMiddleware)
app.add_middleware(LoggingMiddleware)
app.add_middleware(AuditMiddleware)
app.add_middleware(AuthMiddleware)
from api.middleware.operation_gate import OperationGate
app.add_middleware(OperationGate)
from api.middleware.rate_limit import RateLimitMiddleware
app.add_middleware(RateLimitMiddleware)

app.include_router(router)
from core.module_registry import registry
from modules.module_pm.module import manifest as pm_manifest
registry.register(pm_manifest)
from modules.module_pm.application.registration import register_entities as register_pm_entities
register_pm_entities(registry)
from modules.module_daily_work.module import manifest as daily_work_manifest
registry.register(daily_work_manifest)
from modules.module_inventory.module import manifest as inv_manifest
registry.register(inv_manifest)
from modules.module_inventory.application.registration import register_entities as register_inv_entities
register_inv_entities(registry)
from modules.module_hr.module import manifest as hr_manifest
registry.register(hr_manifest)
from modules.module_equipment.module import manifest as equipment_manifest
registry.register(equipment_manifest)
from modules.module_equipment.integrations.inventory_source import (
    validate_fuel_issue,
    validate_fuel_return,
)
registry.register_source_reference("equipment", "fuel_event", validate_fuel_issue)
registry.register_source_reference("equipment", "fuel_return_event", validate_fuel_return)
registry.mount(app)


@app.get("/health")
async def health_check():
    from sqlalchemy import text
    from infrastructure.database.db_context import AsyncSessionLocal
    try:
        async with AsyncSessionLocal() as session:
            version = await session.scalar(text("SELECT version FROM core_schema_versions ORDER BY version DESC LIMIT 1"))
        if not version:
            return JSONResponse({"status": "unavailable"}, status_code=503)
    except Exception:
        return JSONResponse({"status": "unavailable"}, status_code=503)
    return {"status": "healthy", "schema": version}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
