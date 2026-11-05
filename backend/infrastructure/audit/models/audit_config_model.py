from sqlalchemy import Column, String, Boolean, Integer, DateTime, ForeignKey
from infrastructure.database.types import UUID, JSONB
from sqlalchemy.sql import func
from infrastructure.database.db_context import Base
import uuid

class AuditConfigurationModel(Base):
    __tablename__ = "audit_configurations"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    module = Column(String(100), nullable=False)
    entity_type = Column(String(100), nullable=True)
    audit_create = Column(Boolean, default=True)
    audit_update = Column(Boolean, default=True)
    audit_delete = Column(Boolean, default=True)
    audit_view = Column(Boolean, default=False)
    audit_export = Column(Boolean, default=True)
    audit_login = Column(Boolean, default=True)
    detail_level = Column(String(20), default="standard")
    monitored_fields = Column(JSONB, default=list)
    retention_days = Column(Integer, default=365)
    notify_on_critical = Column(Boolean, default=True)
    notify_on_warning = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
