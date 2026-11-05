# infrastructure/database/models/user_session_model.py
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from infrastructure.database.types import UUID
import uuid
from infrastructure.database.db_context import Base


class UserSessionModel(Base):
    __tablename__ = "user_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    session_token = Column(String(500), nullable=False, unique=True, index=True)
    refresh_token = Column(String(500), nullable=False, unique=True, index=True)
    refresh_token_hash = Column(String(64), nullable=True, index=True)
    mfa_verified = Column(Boolean, nullable=False, server_default="false")
    token_kid = Column(String(32), nullable=True)
    ip_address = Column(String(45), nullable=False)
    user_agent = Column(String(255), nullable=True)
    login_time = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    expiry_time = Column(DateTime(timezone=True), nullable=False)
    last_activity = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    is_active = Column(Boolean, nullable=False, server_default="true")
    logout_time = Column(DateTime(timezone=True), nullable=True)

    user = relationship("UserModel", back_populates="sessions")
