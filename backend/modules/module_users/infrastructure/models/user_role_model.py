from sqlalchemy import Column, ForeignKey, UniqueConstraint, Integer, DateTime, func
from sqlalchemy.orm import relationship
from infrastructure.database.types import UUID
from infrastructure.database.db_context import Base  # ✅

class UserRoleModel(Base):
    __tablename__ = "user_roles"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role_id = Column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    __table_args__ = (
        UniqueConstraint("user_id", "role_id", name="uq_user_roles"),
    )
    
    user = relationship("UserModel", back_populates="roles")
    role = relationship("RoleModel", back_populates="users")
