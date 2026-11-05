from datetime import date
from decimal import Decimal
from typing import Optional, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from typing import Annotated

Text = Annotated[str, StringConstraints(strip_whitespace=True, max_length=4000)]
Amount = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=6)]
WorkOrigin = Literal[
    'planned_wep', 'additional_existing_activity',
    'new_project_work', 'independent_project_work',
]
Priority = Literal['low', 'normal', 'high', 'urgent']

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
    # F2 provenance only. The four-way work_origin flow remains F3 except
    # for this explicitly WEP-derived Daily draft item.
    wep_plan_item_id: Optional[UUID] = None
    allocation_key: Annotated[str, StringConstraints(strip_whitespace=True, max_length=80)] = ''
    allocation_reason: Text = ''
    work_origin: Optional[WorkOrigin] = None
    reason_code: Annotated[str, StringConstraints(strip_whitespace=True, max_length=80)] = ''
    reason_note: Text = ''
    priority: Priority = 'normal'
    idempotency_key: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] = ''


class DraftCostInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    estimate_kind: Literal['labor', 'equipment', 'material', 'expense']
    amount: Amount
    currency_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20)]
    fx_as_of: date
    confidence: Literal['high', 'medium', 'low'] = 'medium'


class DraftPreparationInput(BaseModel):
    assignee_user_id: Optional[UUID] = None
    equipment_ids: list[UUID] = Field(default_factory=list, max_length=50)
    estimates: list[DraftCostInput] = Field(default_factory=list, max_length=4)
    readiness_result: Literal['not_checked', 'ready', 'warning', 'blocked'] = 'not_checked'
    requirements_note: Text = ''
    readiness_note: Text = ''
    blocker_type: Annotated[str, StringConstraints(strip_whitespace=True, max_length=80)] = 'operational'
    blocker_description: Text = ''
    priority: Priority = 'normal'


class WepDraftItemInput(DraftPreparationInput):
    """Insert one approved WEP commitment into the Daily Work draft."""
    model_config = ConfigDict(extra='forbid')
    work_date: date
    target_quantity: Amount
    title: Optional[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]] = None
    planned_minutes: Amount = Decimal('0')
    allocation_key: Annotated[str, StringConstraints(strip_whitespace=True, max_length=80)] = ''
    allocation_reason: Text = ''
    team_name: Text = ''
    shift: Text = ''
    location: Text = ''
    notes: Text = ''


class FlexibleDraftItemInput(DraftPreparationInput):
    """Create and prepare a non-WEP Daily draft item atomically."""
    model_config = ConfigDict(extra='forbid')
    work_origin: Literal[
        'additional_existing_activity', 'new_project_work', 'independent_project_work'
    ]
    activity_id: Optional[UUID] = None
    work_date: date
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    target_quantity: Amount = Decimal('0')
    planned_minutes: Amount = Decimal('0')
    unit: Annotated[str, StringConstraints(strip_whitespace=True, max_length=40)] = ''
    reason_code: Annotated[str, StringConstraints(strip_whitespace=True, max_length=80)] = ''
    reason_note: Text = ''
    allocation_key: Annotated[str, StringConstraints(strip_whitespace=True, max_length=80)] = ''
    allocation_reason: Text = ''
    team_name: Text = ''
    shift: Text = ''
    location: Text = ''
    notes: Text = ''
    idempotency_key: Annotated[str, StringConstraints(strip_whitespace=True, min_length=8, max_length=120)]

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
    fx_source: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] = ''

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
