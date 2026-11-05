from pydantic import BaseModel, Field
from typing import Optional, List
from uuid import UUID
from datetime import datetime


class CreateFollowupDTO(BaseModel):
    entity_type: Optional[str] = None
    entity_id: Optional[UUID] = None
    notes: Optional[str] = None
    status_before: Optional[str] = None
    status_after: Optional[str] = None
    progress_percentage: int = 0
    followup_type: str = "manual"
    due_date: Optional[datetime] = None
    category: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    priority_score: int = 0


class UpdateFollowupDTO(BaseModel):
    entity_type: Optional[str] = None
    entity_id: Optional[UUID] = None
    notes: Optional[str] = None
    resolution: Optional[str] = None
    progress_percentage: Optional[int] = None
    status_after: Optional[str] = None
    is_escalated: Optional[bool] = None
    escalated_to: Optional[UUID] = None
    snooze_until: Optional[datetime] = None


class FollowupResponseDTO(BaseModel):
    id: UUID
    user_id: UUID
    entity_type: Optional[str] = None
    entity_id: Optional[UUID] = None
    notes: Optional[str] = None
    status_before: Optional[str] = None
    status_after: Optional[str] = None
    progress_percentage: int
    followup_type: str
    category: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    is_escalated: bool
    priority_score: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True