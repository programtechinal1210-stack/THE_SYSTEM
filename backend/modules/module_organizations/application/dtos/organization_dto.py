from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field

class CreateOrganizationDTO(BaseModel):
    name: str
    parent_id: Optional[UUID] = None

class UpdateOrganizationDTO(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None

class OrganizationResponseDTO(BaseModel):
    id: UUID; name: str; parent_id: Optional[UUID] = None; is_active: bool
    class Config: from_attributes = True
    @classmethod
    def from_entity(cls, entity): return cls(**entity.model_dump())
