from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, ForeignKey
from infrastructure.database.types import UUID, JSONB
from sqlalchemy.sql import func
from infrastructure.database.db_context import Base
import uuid

class SettingCategoryModel(Base):
    __tablename__ = "settings_categories"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(50), unique=True, nullable=False)
    name_ar = Column(String(100), nullable=False)
    name_en = Column(String(100), nullable=False)
    icon = Column(String(50), nullable=True)
    priority = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
