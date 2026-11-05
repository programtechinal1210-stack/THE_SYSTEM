from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey
from infrastructure.database.types import UUID, JSONB
from sqlalchemy.sql import func
from infrastructure.database.db_context import Base
import uuid

class ActivityStreamModel(Base):
    __tablename__ = "activity_stream"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_type = Column(String(50), nullable=False)
    source_id = Column(UUID(as_uuid=True), nullable=True)
    actor_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    actor_name = Column(String(200), nullable=True)
    verb = Column(String(50), nullable=False)
    object_type = Column(String(100), nullable=True)
    object_id = Column(UUID(as_uuid=True), nullable=True)
    object_name = Column(String(500), nullable=True)
    description_ar = Column(Text, nullable=True)
    description_en = Column(Text, nullable=True)
    metadata_json = Column('metadata', JSONB, default=dict)
    target_url = Column(String(500), nullable=True)
    app_version = Column(String(20), nullable=True)
    device_type = Column(String(50), nullable=True)
    location_info = Column(JSONB, default=dict)
    session_id = Column(String(100), nullable=True)
    importance_score = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


