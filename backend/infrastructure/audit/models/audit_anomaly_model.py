from sqlalchemy import Column, String, Text, Boolean, Integer, DateTime, ForeignKey
from infrastructure.database.types import UUID, JSONB, ARRAY
from sqlalchemy import BigInteger
from sqlalchemy.sql import func
from infrastructure.database.db_context import Base
import uuid

class AuditAnomalyTypeModel(Base):
    __tablename__ = "audit_anomaly_types"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(50), unique=True, nullable=False)
    name_ar = Column(String(200), nullable=False)
    name_en = Column(String(200), nullable=True)
    description = Column(Text, nullable=True)
    default_severity = Column(String(20), default="warning")
    detection_rule = Column(JSONB, nullable=False, default=dict)
    auto_notify = Column(Boolean, default=True)
    auto_block = Column(Boolean, default=False)
    auto_create_followup = Column(Boolean, default=False)
    notify_roles = Column(JSONB, default=list)
    notify_channels = Column(JSONB, default=list)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class AuditAnomalyModel(Base):
    __tablename__ = "audit_anomalies"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    anomaly_type_id = Column(UUID(as_uuid=True), ForeignKey("audit_anomaly_types.id"), nullable=False)
    anomaly_type_code = Column(String(50), nullable=True)
    title = Column(String(300), nullable=False)
    description = Column(Text, nullable=True)
    severity = Column(String(20), default="warning")
    related_audit_ids = Column(ARRAY(BigInteger), nullable=True)
    related_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    related_ip = Column(String(50), nullable=True)
    evidence = Column(JSONB, default=dict)
    detection_rule_matched = Column(JSONB, nullable=True)
    resolution_status = Column(String(20), default="open")
    detected_at = Column(DateTime(timezone=True), server_default=func.now())
    detected_by_rule = Column(String(100), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolved_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    resolution_notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

