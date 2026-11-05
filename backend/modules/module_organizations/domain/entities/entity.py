from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field

class Entity(BaseModel):
    model_config = {"from_attributes": True}
    id: Optional[UUID] = None
    name: str = ""
    code: Optional[str] = None
    entity_type_id: Optional[UUID] = None
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    parent_id: Optional[UUID] = None
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
