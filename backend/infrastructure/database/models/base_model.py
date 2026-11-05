from sqlalchemy import Column, DateTime, func
from infrastructure.database.types import UUID
import uuid
from ..db_context import Base

class BaseModel(Base):
    __abstract__ = True
    # تم إزالة id من هنا - سيتم تعريف id في كل نموذج على حدة
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
