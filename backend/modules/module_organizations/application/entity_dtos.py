from datetime import datetime
from uuid import UUID
from typing import Optional
from pydantic import BaseModel

class EntityTypeDTO(BaseModel):
    id: Optional[UUID] = None
    code: str; name: str; description: Optional[str] = None; is_active: bool = True
    class Config: from_attributes = True

class CreateEntityDTO(BaseModel):
    name: str; code: Optional[str] = None; entity_type_id: UUID
    contact_person: Optional[str] = None; phone: Optional[str] = None
    email: Optional[str] = None; address: Optional[str] = None
    parent_id: Optional[UUID] = None

class UpdateEntityDTO(BaseModel):
    name: Optional[str] = None; code: Optional[str] = None
    entity_type_id: Optional[UUID] = None
    contact_person: Optional[str] = None; phone: Optional[str] = None
    email: Optional[str] = None; address: Optional[str] = None
    is_active: Optional[bool] = None
    parent_id: Optional[UUID] = None

class EntityResponseDTO(BaseModel):
    id: UUID; name: str; code: Optional[str] = None; entity_type_id: Optional[UUID] = None
    contact_person: Optional[str] = None; phone: Optional[str] = None
    email: Optional[str] = None; address: Optional[str] = None
    parent_id: Optional[UUID] = None; is_active: bool
    created_at: Optional[datetime] = None; updated_at: Optional[datetime] = None
    class Config: from_attributes = True

