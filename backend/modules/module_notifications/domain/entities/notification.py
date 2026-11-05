from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel

class Notification(BaseModel):
    model_config = {"from_attributes": True}
    id: Optional[UUID] = None
    user_id: UUID
    title: str = ""
    content: str = ""
    type: str = ""
    link: Optional[str] = None
    entity_type: Optional[str] = None
    entity_id: Optional[UUID] = None
    is_read: bool = False
    read_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
