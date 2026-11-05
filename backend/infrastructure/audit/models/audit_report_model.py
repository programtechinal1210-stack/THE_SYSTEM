from sqlalchemy import Column, String, Text, Boolean, Integer, DateTime, ForeignKey
from infrastructure.database.types import UUID, JSONB
from sqlalchemy.sql import func
from infrastructure.database.db_context import Base
import uuid

class AuditReportModel(Base):
    __tablename__ = "audit_reports"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    report_type = Column(String(50), nullable=False)
    filters = Column(JSONB, default=dict)
    date_range_start = Column(DateTime(timezone=True), nullable=True)
    date_range_end = Column(DateTime(timezone=True), nullable=True)
    modules = Column(JSONB, default=list)
    result_data = Column(JSONB, nullable=True)
    summary_ar = Column(Text, nullable=True)
    summary_en = Column(Text, nullable=True)
    key_findings = Column(JSONB, default=list)
    charts = Column(JSONB, default=list)
    status = Column(String(50), default="draft")
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    recipients = Column(JSONB, default=list)
    is_scheduled = Column(Boolean, default=False)
    schedule_cron = Column(String(50), nullable=True)
    schedule_next_run = Column(DateTime(timezone=True), nullable=True)
    is_sent = Column(Boolean, default=False)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    generated_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
