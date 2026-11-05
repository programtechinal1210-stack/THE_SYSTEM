from typing import Optional, List
from uuid import UUID, uuid4
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

class User(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: Optional[UUID] = Field(default_factory=uuid4)
    username: str
    password_hash: str
    full_name: str
    email: str
    phone: Optional[str] = None
    organization_id: Optional[UUID] = None  # جعل اختيارياً
    position: Optional[str] = None
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    _roles: List['Role'] = []
    
    @property
    def roles(self) -> List['Role']:
        return self._roles.copy()
    
    def add_role(self, role: 'Role') -> None:
        if role not in self._roles:
            self._roles.append(role)
    
    def remove_role(self, role: 'Role') -> None:
        if role in self._roles:
            self._roles.remove(role)
    
    def has_permission(self, permission_code: str) -> bool:
        for role in self._roles:
            if role.has_permission(permission_code):
                return True
        return False
    
    def has_role(self, role_name: str) -> bool:
        return any(role.name == role_name for role in self._roles)
    
    def activate(self) -> None:
        self.is_active = True
    
    def deactivate(self) -> None:
        self.is_active = False
