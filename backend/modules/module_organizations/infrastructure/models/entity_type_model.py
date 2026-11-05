from sqlalchemy import Column, String, Text, Boolean, DateTime
from infrastructure.database.types import UUID
from sqlalchemy.sql import func
from infrastructure.database.db_context import Base
import uuid

class EntityTypeModel(Base):
    __tablename__ = "entity_types"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(30), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
