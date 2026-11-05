"""Input contracts for immutable equipment meter events."""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, StringConstraints, field_validator

from .catalog import Input

MeterUnit = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20)]
IdempotencyKey = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
EvidenceRef = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class MeterEventInput(Input):
    meter_type: Literal["hours", "distance", "cycles", "energy"]
    meter_unit: MeterUnit
    event_at: datetime | None = None
    idempotency_key: IdempotencyKey

    @field_validator("event_at")
    @classmethod
    def event_time_must_be_aware(cls, value):
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Timezone-aware timestamp required")
        return value.astimezone(timezone.utc)


class MeterReadingInput(MeterEventInput):
    reading_value: Decimal = Field(ge=0, max_digits=20, decimal_places=6)


class MeterReplacementInput(MeterEventInput):
    old_final_reading: Decimal = Field(ge=0, max_digits=20, decimal_places=6)
    new_initial_reading: Decimal = Field(ge=0, max_digits=20, decimal_places=6)
    reason_code: Reason
    evidence_ref: EvidenceRef


class MeterCorrectionInput(MeterEventInput):
    correction_of_event_id: UUID
    corrected_reading: Decimal = Field(ge=0, max_digits=20, decimal_places=6)
    reason_code: Reason
    evidence_ref: EvidenceRef
