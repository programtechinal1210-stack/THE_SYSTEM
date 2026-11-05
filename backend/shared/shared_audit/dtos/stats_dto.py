from pydantic import BaseModel, Field
from typing import Optional, List, Any
from uuid import UUID
from datetime import datetime, date

class AuditStatsResponse(BaseModel):
    total_actions: int = 0
    avg_duration_ms: Optional[int] = None
    peak_hour: Optional[int] = None
    period_days: int = 30
    generated_at: Optional[datetime] = None
    summary_by_action: dict = Field(default_factory=dict)
    summary_by_severity: dict = Field(default_factory=dict)
    summary_by_module: dict = Field(default_factory=dict)

class AuditTrendResponse(BaseModel):
    date: date
    total_actions: int
    unique_users: int
    critical_count: int
    warning_count: int

class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    skip: int
    limit: int

