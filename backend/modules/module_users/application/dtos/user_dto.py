# modules/module_users/application/dtos/user_dto.py
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, Field


class UserDTO(BaseModel):
    id: UUID = Field(..., description="User ID")
    username: str = Field(..., description="Username")
    full_name: str = Field(..., description="Full name")
    email: str = Field(..., description="Email", pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    phone: Optional[str] = Field(None, description="Phone number")
    organization_id: Optional[UUID] = Field(None, description="Organization ID")
    position: Optional[str] = Field(None, description="Position")
    is_active: bool = Field(True, description="Is active")
    roles: List[str] = Field(default_factory=list, description="Role names")

    class Config:
        from_attributes = True

    @classmethod
    def from_entity(cls, user):
        return cls(
            id=user.id,
            username=user.username,
            full_name=user.full_name,
            email=user.email,
            phone=getattr(user, "phone", None),
            organization_id=user.organization_id,
            position=getattr(user, "position", None),
            is_active=getattr(user, "is_active", True),
            roles=[role.name for role in getattr(user, "roles", [])]
        )


class CreateUserDTO(BaseModel):
    username: str = Field(..., description="Username", max_length=50)
    password: str = Field(..., description="Password", min_length=12)
    full_name: str = Field(..., description="Full name", max_length=200)
    email: str = Field(..., description="Email", pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    phone: Optional[str] = Field(None, description="Phone number")
    organization_id: Optional[UUID] = Field(None, description="Organization ID")
    position: Optional[str] = Field(None, description="Position")
    role_names: List[str] = Field(default_factory=list, description="Role names")


class LoginDTO(BaseModel):
    username: str = Field(..., description="Username")
    password: str = Field(..., description="Password")


class TokenDTO(BaseModel):
    access_token: str = Field(..., description="Access token")
    refresh_token: str = Field(..., description="Refresh token")
    token_type: str = Field("Bearer", description="Token type")
    user_id: UUID = Field(..., description="User ID")
    username: str = Field(..., description="Username")
    full_name: str = Field(..., description="Full name")
    mfa_required: bool = Field(False, description="Second-factor verification pending")


class UpdateUserDTO(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=20)
    position: str | None = Field(default=None, max_length=100)
    is_active: bool | None = None
    email: str | None = Field(default=None, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    organization_id: UUID | None = None
