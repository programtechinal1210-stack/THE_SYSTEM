from sqlalchemy import Column, String, Text, Boolean, DateTime
from infrastructure.database.types import UUID
from sqlalchemy.sql import func
from infrastructure.database.db_context import Base
import uuid

class NotificationTemplateModel(Base):
    __tablename__ = "notification_templates"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type = Column(String(50), unique=True, nullable=False)
    subject_template = Column(Text, nullable=True)
    body_template = Column(Text, nullable=False)
    channel = Column(String(30), default="in_app")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
