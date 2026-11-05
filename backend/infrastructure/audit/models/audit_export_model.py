from sqlalchemy import Column, String, Text, Boolean, Integer, DateTime, ForeignKey
from infrastructure.database.types import UUID, JSONB
from sqlalchemy import BigInteger
from sqlalchemy.sql import func
from infrastructure.database.db_context import Base
import uuid

class AuditExportModel(Base):
    __tablename__ = "audit_exports"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    export_type = Column(String(50), nullable=False)
    export_name = Column(String(200), nullable=True)
    entity_type = Column(String(100), nullable=True)
    date_range_start = Column(DateTime(timezone=True), nullable=True)
    date_range_end = Column(DateTime(timezone=True), nullable=True)
    filters_applied = Column(JSONB, default=dict)
    record_count = Column(Integer, nullable=True)
    file_size_bytes = Column(BigInteger, nullable=True)
    file_path = Column(Text, nullable=True)
    file_hash = Column(String(64), nullable=True)
    status = Column(String(20), default="pending")
    error_message = Column(Text, nullable=True)
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(Text, nullable=True)
    is_downloaded = Column(Boolean, default=False)
    download_count = Column(Integer, default=0)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

