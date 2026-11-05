from sqlalchemy import Column, BigInteger, String, Text, Integer, Boolean, DateTime, ForeignKey
from infrastructure.database.types import UUID, JSONB
from sqlalchemy.sql import func
from infrastructure.database.db_context import Base

class AuditLogModel(Base):
    __tablename__ = "audit_logs"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    action = Column(String(100), nullable=False, index=True)
    entity_type = Column(String(100), nullable=False, index=True)
    entity_id = Column(UUID(as_uuid=True), nullable=True)
    module = Column(String(100), nullable=True, index=True)
    action_type = Column(String(50), default="UPDATE")
    old_value = Column(JSONB, nullable=True)
    new_value = Column(JSONB, nullable=True)
    changes_summary = Column(Text, nullable=True)
    changes_summary_en = Column(Text, nullable=True)
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(Text, nullable=True)
    session_id = Column(String(100), nullable=True)
    severity = Column(String(20), default="info", index=True)
    related_entity_type = Column(String(50), nullable=True)
    related_entity_id = Column(UUID(as_uuid=True), nullable=True)
    metadata_json = Column('metadata', JSONB, default=dict)
    duration_ms = Column(Integer, nullable=True)
    status_code = Column(Integer, nullable=True)
    auth_method = Column(String(50), nullable=True)
    token_id = Column(UUID(as_uuid=True), nullable=True)
    is_system_action = Column(Boolean, default=False)
    impersonated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    mfa_verified = Column(Boolean, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


