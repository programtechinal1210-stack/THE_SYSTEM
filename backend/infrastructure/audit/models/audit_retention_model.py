from sqlalchemy import Column, String, Text, Boolean, Integer, DateTime, ForeignKey
from infrastructure.database.types import UUID, JSONB
from sqlalchemy import BigInteger
from sqlalchemy.sql import func
from infrastructure.database.db_context import Base
import uuid

class AuditRetentionPolicyModel(Base):
    __tablename__ = "audit_retention_policies"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    entity_type = Column(String(100), nullable=False)
    module = Column(String(100), nullable=True)
    retention_days = Column(Integer, nullable=False)
    archive_before_delete = Column(Boolean, default=True)
    archive_retention_days = Column(Integer, nullable=True)
    cleanup_schedule = Column(String(50), nullable=True)
    cleanup_hour = Column(Integer, default=2)
    custom_conditions = Column(JSONB, nullable=True)
    exclude_critical = Column(Boolean, default=True)
    exclude_with_followups = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)
    last_cleanup_at = Column(DateTime(timezone=True), nullable=True)
    last_cleanup_records = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

class AuditCleanupLogModel(Base):
    __tablename__ = "audit_cleanup_logs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    policy_id = Column(UUID(as_uuid=True), ForeignKey("audit_retention_policies.id"), nullable=True)
    entity_type = Column(String(100), nullable=False)
    date_range_start = Column(DateTime(timezone=True), nullable=True)
    date_range_end = Column(DateTime(timezone=True), nullable=True)
    records_archived = Column(Integer, default=0)
    records_deleted = Column(Integer, default=0)
    records_skipped = Column(Integer, default=0)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    status = Column(String(20), default="pending")
    error_message = Column(Text, nullable=True)
    executed_by = Column(String(50), default="system")
    archive_path = Column(Text, nullable=True)
    archive_size_bytes = Column(BigInteger, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

