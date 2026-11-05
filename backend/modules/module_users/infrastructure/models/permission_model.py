from sqlalchemy import Column, String, Integer, DateTime, func
from sqlalchemy.orm import relationship
from infrastructure.database.db_context import Base  # ✅

class PermissionModel(Base):
    __tablename__ = "permissions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(50), nullable=False, unique=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(String(255), nullable=True)
    system = Column(String(50), nullable=False)
    resource = Column(String(50), nullable=False)
    action = Column(String(30), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    roles = relationship("RolePermissionModel", back_populates="permission", cascade="all, delete-orphan")
