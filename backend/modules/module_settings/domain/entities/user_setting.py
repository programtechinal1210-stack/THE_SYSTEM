from datetime import datetime
from typing import Optional, Any
from uuid import UUID
from pydantic import BaseModel

class UserSetting(BaseModel):
    model_config = {"from_attributes": True}
    id: Optional[UUID] = None; user_id: UUID; setting_key: str = ""
    value: Any = None; created_at: Optional[datetime] = None; updated_at: Optional[datetime] = None
