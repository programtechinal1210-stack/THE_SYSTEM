from typing import Optional, List
from uuid import UUID
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, text
from ..models.audit_log_model import AuditLogModel
from shared.shared_audit.dtos.audit_dto import CreateAuditLogDTO, AuditLogDTO, AuditFilterDTO
from shared.shared_audit.dtos.stats_dto import AuditStatsResponse, PaginatedResponse

class AuditService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def log(self, data: CreateAuditLogDTO) -> AuditLogDTO:
        model = AuditLogModel(**data.model_dump(exclude_none=True))
        self.session.add(model)
        await self.session.flush()
        return AuditLogDTO(
            id=model.id, user_id=model.user_id, action=model.action,
            entity_type=model.entity_type, entity_id=model.entity_id,
            module=model.module, changes_summary=model.changes_summary,
            severity=model.severity, ip_address=model.ip_address,
            created_at=model.created_at
        )

    async def get_logs(self, filters: AuditFilterDTO) -> PaginatedResponse:
        stmt = select(AuditLogModel)
        conditions = []
        if filters.module: conditions.append(AuditLogModel.module == filters.module)
        if filters.action: conditions.append(AuditLogModel.action == filters.action)
        if filters.entity_type: conditions.append(AuditLogModel.entity_type == filters.entity_type)
        if filters.severity: conditions.append(AuditLogModel.severity == filters.severity)
        if filters.user_id: conditions.append(AuditLogModel.user_id == filters.user_id)
        if filters.date_from: conditions.append(AuditLogModel.created_at >= filters.date_from)
        if filters.date_to: conditions.append(AuditLogModel.created_at <= filters.date_to)
        if filters.search:
            search = f"%{filters.search}%"
            conditions.append(AuditLogModel.changes_summary.ilike(search))
        
        if conditions: stmt = stmt.where(and_(*conditions))
        
        count_stmt = select(func.count()).select_from(AuditLogModel)
        if conditions: count_stmt = count_stmt.where(and_(*conditions))
        total = (await self.session.execute(count_stmt)).scalar() or 0
        
        stmt = stmt.order_by(AuditLogModel.created_at.desc()).offset(filters.skip).limit(filters.limit)
        result = await self.session.execute(stmt)
        items = [
            AuditLogDTO(
                id=m.id, user_id=m.user_id, action=m.action,
                entity_type=m.entity_type, entity_id=m.entity_id,
                module=m.module, changes_summary=m.changes_summary,
                severity=m.severity, ip_address=m.ip_address,
                created_at=m.created_at
            ) for m in result.scalars().all()
        ]
        return PaginatedResponse(items=items, total=total, skip=filters.skip, limit=filters.limit)

    async def get_summary(self, date_from=None, date_to=None, module=None, user_id=None) -> AuditStatsResponse:
        stmt = select(func.count()).select_from(AuditLogModel)
        total = (await self.session.execute(stmt)).scalar() or 0
        return AuditStatsResponse(total_actions=total)
