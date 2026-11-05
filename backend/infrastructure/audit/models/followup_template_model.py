from sqlalchemy import Column, String, Text, Boolean, Integer, DateTime, ForeignKey
from infrastructure.database.types import UUID, JSONB
from sqlalchemy.sql import func
from infrastructure.database.db_context import Base
import uuid

class FollowupTemplateModel(Base):
    __tablename__ = "followup_templates"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    category_id = Column(UUID(as_uuid=True), ForeignKey("followup_categories.id"), nullable=True)
    default_title = Column(String(300), nullable=True)
    default_notes = Column(Text, nullable=True)
    default_priority = Column(String(20), default="normal")
    default_due_days = Column(Integer, nullable=True)
    default_tags = Column(JSONB, default=list)
    auto_escalate = Column(Boolean, default=False)
    escalate_after_days = Column(Integer, nullable=True)
    escalate_to_role_id = Column(Integer, ForeignKey("roles.id"), nullable=True)
    send_reminders = Column(Boolean, default=True)
    reminder_interval_hours = Column(Integer, default=24)
    max_reminders = Column(Integer, default=3)
    is_active = Column(Boolean, default=True)
    is_system = Column(Boolean, default=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
