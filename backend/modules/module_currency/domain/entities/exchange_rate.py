from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel


class ExchangeRate(BaseModel):
    model_config = {"from_attributes": True}
    id: Optional[UUID] = None
    from_currency: Optional[UUID] = None
    to_currency: Optional[UUID] = None
    rate: float = 1.0
    effective_date: Optional[str] = None
    source: str = "manual"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
