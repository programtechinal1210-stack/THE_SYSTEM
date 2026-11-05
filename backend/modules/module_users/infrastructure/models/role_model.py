# # إعادة تصدير النموذج من الموقع العام
# from infrastructure.database.models.role_model import RoleModel
from sqlalchemy import Column, String, Boolean, Integer, DateTime, func
from sqlalchemy.orm import relationship
from infrastructure.database.db_context import Base  # ✅

class RoleModel(Base):
    __tablename__ = "roles"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False, unique=True, index=True)
    description = Column(String(255), nullable=True)
    is_system = Column(Boolean, nullable=False, server_default="false")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    
    users = relationship("UserRoleModel", back_populates="role", cascade="all, delete-orphan")
    permissions = relationship("RolePermissionModel", back_populates="role", cascade="all, delete-orphan")
