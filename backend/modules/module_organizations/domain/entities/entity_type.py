from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field

class EntityType(BaseModel):
    model_config = {"from_attributes": True}
    id: Optional[UUID] = None
    code: str = ""
    name: str = ""
    description: Optional[str] = None
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
