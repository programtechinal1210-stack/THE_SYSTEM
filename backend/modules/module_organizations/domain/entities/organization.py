from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field

class Organization(BaseModel):
    model_config = {"from_attributes": True}
    id: Optional[UUID] = None
    name: str = ""
    parent_id: Optional[UUID] = None
    is_active: bool = True
