from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID
from datetime import datetime

class AuditLogDTO(BaseModel):
    id: int
    user_id: Optional[UUID] = None
    action: str
    entity_type: str
    entity_id: Optional[UUID] = None
    module: Optional[str] = None
    changes_summary: Optional[str] = None
    severity: str = "info"
    ip_address: Optional[str] = None
    created_at: Optional[datetime] = None
    class Config: from_attributes = True

class CreateAuditLogDTO(BaseModel):
    user_id: Optional[UUID] = None
    action: str
    entity_type: str
    entity_id: Optional[UUID] = None
    module: Optional[str] = None
    action_type: str = "UPDATE"
    old_value: Optional[dict] = None
    new_value: Optional[dict] = None
    changes_summary: Optional[str] = None
    changes_summary_en: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    session_id: Optional[str] = None
    severity: str = "info"
    related_entity_type: Optional[str] = None
    related_entity_id: Optional[UUID] = None
    meta_data: dict = Field(default_factory=dict)
    duration_ms: Optional[int] = None
    status_code: Optional[int] = None
    auth_method: Optional[str] = None
    token_id: Optional[UUID] = None
    is_system_action: bool = False

class AuditFilterDTO(BaseModel):
    module: Optional[str] = None
    action: Optional[str] = None
    entity_type: Optional[str] = None
    severity: Optional[str] = None
    user_id: Optional[UUID] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    search: Optional[str] = None
    skip: int = 0
    limit: int = 50

