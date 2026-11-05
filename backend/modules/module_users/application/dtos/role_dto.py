# modules/module_users/application/dtos/role_dto.py
from typing import Optional, List
from pydantic import BaseModel, Field


class RoleDTO(BaseModel):
    id: int = Field(..., description="Role ID")
    name: str = Field(..., description="Role name")
    description: Optional[str] = Field(None, description="Role description")

    class Config:
        from_attributes = True

    @classmethod
    def from_entity(cls, role):
        return cls(
            id=role.id,
            name=role.name,
            description=getattr(role, "description", None)
        )


class CreateRoleDTO(BaseModel):
    name: str = Field(..., description="Role name", max_length=50)
    description: Optional[str] = Field(None, description="Role description")
    permission_ids: Optional[List[int]] = Field(default=[], description="Permission IDs")


class UpdateRoleDTO(BaseModel):
    name: Optional[str] = Field(None, description="Role name", max_length=50)
    description: Optional[str] = Field(None, description="Role description")
    permission_ids: Optional[List[int]] = Field(None, description="Permission IDs")
