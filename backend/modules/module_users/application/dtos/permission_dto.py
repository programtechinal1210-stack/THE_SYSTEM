from typing import Optional
from pydantic import BaseModel, Field


class PermissionDTO(BaseModel):
    id: int = Field(..., description="Permission ID")
    code: str = Field(..., description="Permission code")
    name: str = Field(..., description="Permission name")
    description: Optional[str] = Field(None, description="Permission description")
    system: str = Field(..., description="System")
    resource: str = Field(..., description="Resource")
    action: str = Field(..., description="Action")

    class Config:
        from_attributes = True

    @classmethod
    def from_entity(cls, permission):
        return cls(
            id=permission.id,
            code=permission.code,
            name=permission.name,
            description=getattr(permission, "description", None),
            system=permission.system,
            resource=permission.resource,
            action=permission.action
        )


class CreatePermissionDTO(BaseModel):
    code: str = Field(..., description="Permission code", max_length=50)
    name: str = Field(..., description="Permission name", max_length=100)
    description: Optional[str] = Field(None, description="Permission description")
    system: str = Field("goms", description="System name")
    resource: str = Field(..., description="Resource name")
    action: str = Field(..., description="Action")
