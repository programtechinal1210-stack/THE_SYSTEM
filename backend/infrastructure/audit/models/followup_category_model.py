from sqlalchemy import Column, String, Text, Boolean, Integer, DateTime
from infrastructure.database.types import UUID
from sqlalchemy.sql import func
from infrastructure.database.db_context import Base
import uuid

class FollowupCategoryModel(Base):
    __tablename__ = "followup_categories"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(50), unique=True, nullable=False)
    name_ar = Column(String(100), nullable=False)
    name_en = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)
    icon = Column(String(50), nullable=True)
    color = Column(String(20), default="#6B7280")
    default_priority = Column(String(20), default="normal")
    default_due_days = Column(Integer, nullable=True)
    auto_escalate = Column(Boolean, default=False)
    escalate_after_days = Column(Integer, nullable=True)
    priority = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    is_system = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
