from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel

class UserNotificationSetting(BaseModel):
    model_config = {"from_attributes": True}
    id: Optional[UUID] = None; user_id: UUID; notification_type: str = ""
    channel: str = "in_app"; is_enabled: bool = True
    created_at: Optional[datetime] = None; updated_at: Optional[datetime] = None
