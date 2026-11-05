from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel

class NotificationTemplate(BaseModel):
    model_config = {"from_attributes": True}
    id: Optional[UUID] = None; type: str = ""; subject_template: Optional[str] = None
    body_template: str = ""; channel: str = "in_app"; is_active: bool = True
    created_at: Optional[datetime] = None; updated_at: Optional[datetime] = None
