from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Optional, List
from datetime import datetime

from infrastructure.database.db_context import get_session
from api.dependencies import get_current_user
from modules.module_users.domain.entities.user import User
from infrastructure.audit.services.audit_service import AuditService
from shared.shared_audit.dtos.audit_dto import AuditFilterDTO, AuditLogDTO
from shared.shared_audit.dtos.stats_dto import AuditStatsResponse, PaginatedResponse

router = APIRouter(prefix="/logs", tags=["audit-logs"])

def get_audit_service(s: AsyncSession = Depends(get_session, scope="function")): return AuditService(s)

@router.get("", response_model=PaginatedResponse)
async def list_logs(
    module: Optional[str] = None, action: Optional[str] = None,
    entity_type: Optional[str] = None, severity: Optional[str] = None,
    user_id: Optional[UUID] = None, search: Optional[str] = None,
    date_from: Optional[datetime] = None, date_to: Optional[datetime] = None,
    skip: int = 0, limit: int = 100000,
    u: User = Depends(get_current_user), svc = Depends(get_audit_service)
):
    filters = AuditFilterDTO(module=module, action=action, entity_type=entity_type,
        severity=severity, user_id=user_id, search=search, date_from=date_from, date_to=date_to, skip=skip, limit=limit)
    return await svc.get_logs(filters)

@router.get("/summary", response_model=AuditStatsResponse)
async def audit_summary(
    date_from: Optional[datetime] = None, date_to: Optional[datetime] = None,
    module: Optional[str] = None, user_id: Optional[UUID] = None,
    u: User = Depends(get_current_user), svc = Depends(get_audit_service)
):
    return await svc.get_summary(date_from, date_to, module, user_id)
