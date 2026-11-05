from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, StringConstraints, field_validator, model_validator

from .catalog import Input

RequiredText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class SafetyPolicyInput(Input):
    organization_id: UUID
    policy_version: int = Field(ge=1)
    policy_mode: Literal["test", "production"]
    policy_reference: RequiredText
    policy_document_ref: RequiredText
    issuing_authority: RequiredText
    authorized_role_code: RequiredText
    effective_from: datetime
    effective_until: datetime | None = None
    inspection_validity_minutes: int = Field(ge=1, le=1440)

    @field_validator("effective_from", "effective_until")
    @classmethod
    def timestamps_are_aware(cls, value):
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("Timezone-aware timestamp required")
        return value

    @model_validator(mode="after")
    def validity_interval_is_ordered(self):
        if self.effective_until and self.effective_until <= self.effective_from:
            raise ValueError("effective_until must be later than effective_from")
        return self


class SafetyPolicyDecision(Input):
    decision_authority_ref: RequiredText


class OperationStartInput(Input):
    assignment_id: UUID
    shift_roster_id: UUID
    policy_id: UUID
    idempotency_key: RequiredText
    notes: Annotated[str, StringConstraints(max_length=2000)] = ""


class OperationFinishInput(Input):
    meter_end: Decimal | None = Field(default=None, ge=0, max_digits=20, decimal_places=6)
    working_minutes: int = Field(ge=0)
    idle_minutes: int = Field(ge=0)
    downtime_minutes: int = Field(ge=0)
    produced_quantity: Decimal | None = Field(default=None, ge=0, max_digits=20, decimal_places=6)
    production_unit: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)] | None = None
    fuel_consumed: Decimal | None = Field(default=None, gt=0, max_digits=20, decimal_places=6)
    fuel_energy_type: Literal["diesel", "gasoline", "electricity", "other"] | None = None
    fuel_unit: Literal["L", "kWh", "kg", "m3"] | None = None
    downtime_reason_code: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] | None = None
    downtime_notes: Annotated[str, StringConstraints(max_length=2000)] = ""
    notes: Annotated[str, StringConstraints(max_length=2000)] = ""

    @model_validator(mode="after")
    def paired_fields(self):
        if (self.produced_quantity is None) != (self.production_unit is None):
            raise ValueError("Production quantity and unit must be supplied together")
        if (self.fuel_consumed is None) != (self.fuel_energy_type is None):
            raise ValueError("Fuel consumption and energy type must be supplied together")
        if (self.fuel_consumed is None) != (self.fuel_unit is None):
            raise ValueError("Fuel consumption and unit must be supplied together")
        if self.downtime_minutes and not self.downtime_reason_code:
            raise ValueError("Downtime reason is required when downtime is recorded")
        return self
