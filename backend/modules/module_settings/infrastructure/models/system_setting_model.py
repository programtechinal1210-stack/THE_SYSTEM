from sqlalchemy import Column, String, Boolean, DateTime, Text, ForeignKey
from infrastructure.database.types import UUID, JSONB
from sqlalchemy.sql import func
from infrastructure.database.db_context import Base
import uuid

class SystemSettingModel(Base):
    __tablename__ = "system_settings"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key = Column(String(100), unique=True, nullable=False)
    category_id = Column(UUID(as_uuid=True), ForeignKey("settings_categories.id"), nullable=True)
    value = Column(JSONB, nullable=False)
    default_value = Column(JSONB, nullable=True)
    data_type = Column(String(20), default="string")
    description_ar = Column(Text, nullable=True)
    description_en = Column(Text, nullable=True)
    is_encrypted = Column(Boolean, default=False)
    is_required = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)
    validation_rules = Column(JSONB, nullable=True)
    options = Column(JSONB, nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
