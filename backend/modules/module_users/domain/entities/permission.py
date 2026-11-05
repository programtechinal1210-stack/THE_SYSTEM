from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field

class Permission(BaseModel):
    model_config = {"from_attributes": True}
    
    id: Optional[int] = None  # تغيير من UUID إلى int
    code: str
    name: str
    description: Optional[str] = None
    system: str
    resource: str
    action: str
    created_at: Optional[datetime] = None
