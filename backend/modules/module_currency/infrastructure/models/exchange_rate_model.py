import uuid

from sqlalchemy import Column, DateTime, Float, ForeignKey, String
from sqlalchemy.sql import func

from infrastructure.database.db_context import Base
from infrastructure.database.types import UUID


class ExchangeRateModel(Base):
    __tablename__ = "core_exchange_rates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    from_currency = Column(UUID(as_uuid=True), ForeignKey("core_currencies.id"), nullable=False)
    to_currency = Column(UUID(as_uuid=True), ForeignKey("core_currencies.id"), nullable=False)
    rate = Column(Float, nullable=False)
    rate_decimal = Column(String, nullable=False)
    effective_date = Column(String, nullable=False)
    source = Column(String(50), default="manual")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
