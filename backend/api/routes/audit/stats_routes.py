from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime

from infrastructure.database.db_context import get_session
from api.dependencies import get_current_user
from modules.module_users.domain.entities.user import User
from infrastructure.audit.services.audit_service import AuditService
from infrastructure.audit.models.audit_anomaly_model import AuditAnomalyModel
from infrastructure.audit.models.audit_alert_model import AuditAlertModel
from infrastructure.audit.models.audit_export_model import AuditExportModel
from shared.shared_audit.dtos.stats_dto import AuditStatsResponse

router = APIRouter(prefix="/stats", tags=["audit-stats"])

def get_svc(s: AsyncSession = Depends(get_session, scope="function")): return AuditService(s)

class AnomalyDTO(BaseModel):
    id: UUID; title: str; anomaly_type_code: Optional[str] = None; severity: str
    resolution_status: str; detected_at: Optional[datetime] = None
    class Config: from_attributes = True

class AlertDTO(BaseModel):
    id: UUID; name: str; module: Optional[str] = None; severity_threshold: str
    is_active: bool; last_triggered_at: Optional[datetime] = None
    class Config: from_attributes = True

class ExportDTO(BaseModel):
    id: UUID; export_type: str; export_name: Optional[str] = None; status: str
    record_count: Optional[int] = None; file_size_bytes: Optional[int] = None
    created_at: Optional[datetime] = None
    class Config: from_attributes = True

@router.get("/summary", response_model=AuditStatsResponse)
async def get_stats(
    date_from: Optional[datetime] = None, date_to: Optional[datetime] = None,
    module: Optional[str] = None, user_id: Optional[UUID] = None,
    u: User = Depends(get_current_user), svc = Depends(get_svc)
):
    return await svc.get_summary(date_from, date_to, module, user_id)

@router.get("/anomalies", response_model=List[AnomalyDTO])
async def list_anomalies(skip: int=0, limit: int=20, s: AsyncSession = Depends(get_session, scope="function")):
    from sqlalchemy import select
    r = await s.execute(select(AuditAnomalyModel).offset(skip).limit(limit).order_by(AuditAnomalyModel.detected_at.desc()))
    return [AnomalyDTO.model_validate(m) for m in r.scalars().all()]

@router.get("/alerts", response_model=List[AlertDTO])
async def list_alerts(skip: int=0, limit: int=20, s: AsyncSession = Depends(get_session, scope="function")):
    from sqlalchemy import select
    r = await s.execute(select(AuditAlertModel).offset(skip).limit(limit).order_by(AuditAlertModel.created_at.desc()))
    return [AlertDTO.model_validate(m) for m in r.scalars().all()]

@router.get("/exports", response_model=List[ExportDTO])
async def list_exports(skip: int=0, limit: int=20, s: AsyncSession = Depends(get_session, scope="function")):
    from sqlalchemy import select
    r = await s.execute(select(AuditExportModel).offset(skip).limit(limit).order_by(AuditExportModel.created_at.desc()))
    return [ExportDTO.model_validate(m) for m in r.scalars().all()]
