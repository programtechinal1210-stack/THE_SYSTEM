from sqlalchemy import Column, String, Boolean, DateTime
from infrastructure.database.types import UUID
from sqlalchemy.sql import func
from infrastructure.database.db_context import Base
import uuid

class NotificationChannelModel(Base):
    __tablename__ = "notification_channels"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(30), unique=True, nullable=False)
    name_ar = Column(String(50), nullable=False)
    name_en = Column(String(50), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
