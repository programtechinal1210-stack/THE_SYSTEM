"""Input contracts for EMO assignment and safety workflows."""
import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, StringConstraints, field_validator, model_validator

from .catalog import Input

RequiredText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


def _aware(value):
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Timezone-aware timestamp required")
    return value.astimezone(timezone.utc)


class AssignmentInput(Input):
    asset_id: UUID
    request_id: UUID | None = None
    operator_employee_id: UUID | None = None
    beneficiary_entity_id: UUID
    purpose: RequiredText
    planned_start_at: datetime
    planned_end_at: datetime
    idempotency_key: ShortText

    @field_validator("planned_start_at", "planned_end_at")
    @classmethod
    def timestamps_must_be_aware(cls, value):
        return _aware(value)

    @model_validator(mode="after")
    def period_is_valid(self):
        if self.planned_start_at >= self.planned_end_at:
            raise ValueError("planned_end_at must be later than planned_start_at")
        return self


class EquipmentRequestInput(Input):
    requested_entity_id: UUID
    category_id: UUID
    required_quantity: int = Field(gt=0, le=10000)
    required_start: datetime
    required_end: datetime
    required_specs: dict = Field(default_factory=dict)
    target_location: Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)] = ""
    purpose: RequiredText
    priority: Literal["low", "normal", "high", "critical"] = "normal"

    @field_validator("required_start", "required_end")
    @classmethod
    def request_timestamps_must_be_aware(cls, value):
        return _aware(value)

    @field_validator("required_specs")
    @classmethod
    def request_specs_must_be_bounded(cls, value):
        if len(json.dumps(value, ensure_ascii=False)) > 16000:
            raise ValueError("required_specs exceeds 16000 characters")
        return value

    @model_validator(mode="after")
    def request_period_is_valid(self):
        if self.required_start >= self.required_end:
            raise ValueError("required_end must be later than required_start")
        return self


class RequestDecisionInput(Input):
    decision_reason: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] = ""


class MovementInput(Input):
    asset_id: UUID
    from_entity_id: UUID
    to_entity_id: UUID
    from_location: Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)] = ""
    to_location: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
    movement_reason: RequiredText
    idempotency_key: ShortText

    @model_validator(mode="after")
    def endpoints_must_differ(self):
        if self.from_entity_id == self.to_entity_id and self.from_location == self.to_location:
            raise ValueError("Movement source and destination must differ")
        return self


class MovementReceiptInput(Input):
    condition_at_receipt: RequiredText


class InspectionInput(Input):
    asset_id: UUID
    assignment_id: UUID | None = None
    inspection_type: Literal["pre_operation", "post_repair", "periodic", "return"]
    result: Literal["passed", "conditional", "failed"]
    critical_failure: bool = False
    checklist_version: ShortText
    findings: dict = Field(default_factory=dict)
    meter_reading: Decimal | None = Field(default=None, ge=0, max_digits=20, decimal_places=6)
    inspected_at: datetime | None = None

    @field_validator("inspected_at")
    @classmethod
    def inspection_timestamp_must_be_aware(cls, value):
        return None if value is None else _aware(value)

    @model_validator(mode="after")
    def critical_failure_must_fail(self):
        if self.critical_failure and self.result != "failed":
            raise ValueError("critical_failure requires a failed result")
        if self.inspection_type == "pre_operation" and self.assignment_id is None:
            raise ValueError("pre-operation inspection requires an assignment")
        return self


class MaintenanceInput(Input):
    asset_id: UUID
    maintenance_type: Literal["preventive", "corrective", "emergency"]
    description: RequiredText


class MaintenanceCompletionInput(Input):
    completion_notes: RequiredText


class SafetyReleaseInput(Input):
    inspection_id: UUID
