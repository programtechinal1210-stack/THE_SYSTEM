from sqlalchemy import Column, String, Text, Integer, Boolean, DateTime, ForeignKey
from infrastructure.database.types import UUID, JSONB
from sqlalchemy.sql import func
from infrastructure.database.db_context import Base
import uuid

class ExecutionHistoryModel(Base):
    __tablename__ = "execution_history"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type = Column(String(50), nullable=False, index=True)
    entity_id = Column(UUID(as_uuid=True), nullable=False)
    action = Column(String(50), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    old_data = Column(JSONB, nullable=True)
    new_data = Column(JSONB, nullable=True)
    notes = Column(Text, nullable=True)
    execution_type = Column(String(50), default="status_change")
    duration_seconds = Column(Integer, nullable=True)
    is_delayed = Column(Boolean, default=False)
    delay_reason = Column(Text, nullable=True)
    location_info = Column(JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
