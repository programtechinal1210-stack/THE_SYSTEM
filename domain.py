from datetime import date
from decimal import Decimal
from typing import Optional, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from typing import Annotated

Text = Annotated[str, StringConstraints(strip_whitespace=True, max_length=4000)]
Amount = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=6)]

class DailyWorkInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    activity_id: UUID
    work_order_id: Optional[UUID] = None
    work_date: date
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    target_quantity: Amount = Decimal('0')
    unit: str = ''
    assignee_user_id: Optional[UUID] = None
    team_name: str = ''
    shift: str = ''
    location: str = ''
    notes: str = ''

class ProgressInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    quantity: Amount
    notes: str = ''

class BlockerInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    blocker_type: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    description: Annotated[str, StringConstraints(min_length=1, max_length=4000)]

class ResolveInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    note: str = ''

class StatusInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    status: str

class ReadinessInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    check_type: Annotated[str, StringConstraints(min_length=1, max_length=80)] = 'general'
    result: str
    note: str = ''

class PlanCreateInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    plan_date: date
    period_start: date
    period_end: date
    owner_user_id: Optional[UUID] = None

class PlanItemInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    activity_id: Optional[UUID] = None
    work_order_id: Optional[UUID] = None
    work_date: date
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    target_quantity: Amount = Decimal('0')
    planned_minutes: Amount = Decimal('0')
    unit: Annotated[str, StringConstraints(strip_whitespace=True, max_length=40)] = ''
    source_type: Literal['pm_activity', 'pm_work_order', 'independent'] = 'pm_activity'
    assignee_user_id: Optional[UUID] = None
    team_name: Text = ''
    shift: Text = ''
    location: Text = ''
    emergency_flag: bool = False
    emergency_reason: Text = ''
    notes: Text = ''

class EstimateInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    estimate_kind: str
    quantity: Amount
    unit: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
    unit_rate: Amount
    currency_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20)]
    fx_rate: Decimal = Decimal('1')
    fx_as_of: date
    confidence: str = 'medium'

class ActualUpdateInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    event_type: Literal['quantity', 'time', 'cost']
    value: Decimal = Field(ge=0, max_digits=18, decimal_places=6)
    unit: Annotated[str, StringConstraints(strip_whitespace=True, max_length=40)] = ''
    currency_id: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=20)]] = None
    fx_rate: Decimal = Field(default=Decimal('1'), gt=0, max_digits=18, decimal_places=8)
    occurred_at: Optional[str] = None
    idempotency_key: Annotated[str, StringConstraints(strip_whitespace=True, min_length=8, max_length=120)]
    note: Text = ''

class PlanCloseInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    summary: Text = ''
    idempotency_key: Annotated[str, StringConstraints(strip_whitespace=True, min_length=8, max_length=120)]

class PlanReopenInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=4000)]
    idempotency_key: Annotated[str, StringConstraints(strip_whitespace=True, min_length=8, max_length=120)]

class EvidenceInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    evidence_type: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
    local_storage_key: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
    sha256: Annotated[str, StringConstraints(pattern=r'^[A-Fa-f0-9]{64}$')]
    content_type: Annotated[str, StringConstraints(max_length=120)] = ''
    size_bytes: Optional[int] = Field(default=None, ge=0)
    captured_at: Optional[str] = None

class AssignmentInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    subject_type: Literal['user', 'team', 'equipment']
    subject_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    role: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)] = 'worker'
    is_lead: bool = False
    planned_minutes: Amount = Decimal('0')
