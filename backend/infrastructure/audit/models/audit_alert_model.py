from sqlalchemy import Column, String, Text, Boolean, Integer, DateTime, ForeignKey
from infrastructure.database.types import UUID, JSONB
from sqlalchemy.sql import func
from infrastructure.database.db_context import Base
import uuid

class AuditAlertModel(Base):
    __tablename__ = "audit_alerts"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    module = Column(String(100), nullable=True)
    action_type = Column(String(50), nullable=True)
    entity_type = Column(String(100), nullable=True)
    severity_threshold = Column(String(20), default="warning")
    conditions = Column(JSONB, default=dict)
    cooldown_minutes = Column(Integer, default=60)
    notify_users = Column(JSONB, default=list)
    notify_roles = Column(JSONB, default=list)
    notify_channels = Column(JSONB, default=list)
    is_active = Column(Boolean, default=True)
    last_triggered_at = Column(DateTime(timezone=True), nullable=True)
    trigger_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
