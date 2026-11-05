from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel


class Currency(BaseModel):
    model_config = {"from_attributes": True}
    id: Optional[UUID] = None
    code: str = ""
    name: str = ""
    symbol: str = ""
    is_anchor: bool = False
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
