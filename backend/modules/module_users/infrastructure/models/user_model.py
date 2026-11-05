# # إعادة تصدير النموذج من الموقع العام
# from infrastructure.database.models.user_model import UserModel

# # إضافة أي دوال مساعدة خاصة بالوحدة هنا إذا لزم الأمر
# infrastructure/database/models/user_model.py
from sqlalchemy import Column, String, Boolean, ForeignKey, DateTime, func
from sqlalchemy.orm import relationship
from infrastructure.database.types import UUID
import uuid
from infrastructure.database.db_context import Base


class UserModel(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(50), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(200), nullable=False)
    email = Column(String(255), nullable=False, unique=True, index=True)
    phone = Column(String(20), nullable=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    position = Column(String(100), nullable=True)
    is_active = Column(Boolean, nullable=False, server_default="true")
    mfa_secret = Column(String(64), nullable=True)
    mfa_enabled = Column(Boolean, nullable=False, server_default="false")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    organization = relationship("OrganizationModel", back_populates="users")
    roles = relationship("UserRoleModel", back_populates="user", cascade="all, delete-orphan")
    sessions = relationship("UserSessionModel", back_populates="user", cascade="all, delete-orphan")
