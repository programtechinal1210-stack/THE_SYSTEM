from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field

class Role(BaseModel):
    model_config = {"from_attributes": True}
    
    id: Optional[int] = None  # تغيير من UUID إلى int
    name: str
    description: Optional[str] = None
    is_system: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    _permissions: List['Permission'] = []
    
    @property
    def permissions(self) -> List['Permission']:
        return self._permissions.copy()
    
    def add_permission(self, permission: 'Permission') -> None:
        if permission not in self._permissions:
            self._permissions.append(permission)
    
    def remove_permission(self, permission: 'Permission') -> None:
        if permission in self._permissions:
            self._permissions.remove(permission)
    
    def has_permission(self, permission_code: str) -> bool:
        return any(p.code == permission_code for p in self._permissions)
