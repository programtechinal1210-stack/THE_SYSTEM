from sqlalchemy import Column, String, Text, Integer, Boolean, DateTime, ForeignKey
from infrastructure.database.types import UUID, JSONB
from sqlalchemy.sql import func
from infrastructure.database.db_context import Base
import uuid


class FollowUpModel(Base):
    """
    Generic Core follow-up record.

    A follow-up can point to an entity owned by any future business module
    through entity_type + entity_id without a hard FK to that module.
    """

    __tablename__ = "follow_ups"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    entity_type = Column(String(100), nullable=True, index=True)
    entity_id = Column(UUID(as_uuid=True), nullable=True, index=True)

    notes = Column(Text, nullable=True)
    status_before = Column(String(50), nullable=True)
    status_after = Column(String(50), nullable=True)
    progress_percentage = Column(Integer, default=0)
    followup_type = Column(String(50), default="manual")
    due_date = Column(DateTime(timezone=True), nullable=True)
    resolution = Column(Text, nullable=True)

    resolved_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    is_escalated = Column(Boolean, default=False)
    escalated_to = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )
    escalated_at = Column(DateTime(timezone=True), nullable=True)

    category = Column(String(50), nullable=True)
    tags = Column(JSONB, default=list)

    reminder_sent_at = Column(DateTime(timezone=True), nullable=True)
    reminder_count = Column(Integer, default=0)
    snooze_until = Column(DateTime(timezone=True), nullable=True)
    auto_resolve = Column(Boolean, default=False)
    priority_score = Column(Integer, default=0)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )