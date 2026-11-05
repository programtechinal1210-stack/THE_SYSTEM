from sqlalchemy import Column, String, Boolean, ForeignKey
from infrastructure.database.types import UUID
from sqlalchemy.orm import relationship
from infrastructure.database.db_context import Base
import uuid


class OrganizationModel(Base):
    __tablename__ = "organizations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    parent_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True)
    is_active = Column(Boolean, default=True)

    parent = relationship("OrganizationModel", remote_side=[id], back_populates="children")
    children = relationship("OrganizationModel", back_populates="parent")
    users = relationship("UserModel", back_populates="organization")
