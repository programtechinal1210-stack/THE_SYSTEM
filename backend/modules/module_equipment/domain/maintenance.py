"""Input contracts for preventive maintenance plans."""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import Field, StringConstraints, field_validator, model_validator

from .catalog import Input

RequiredText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
IdempotencyKey = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class MaintenancePlanInput(Input):
    asset_id: UUID
    description: RequiredText
    interval_days: int | None = Field(default=None, gt=0, le=36500)
    interval_meter: Decimal | None = Field(default=None, gt=0, max_digits=20, decimal_places=6)
    first_due_at: datetime | None = None
    first_due_meter: Decimal | None = Field(default=None, ge=0, max_digits=20, decimal_places=6)
    idempotency_key: IdempotencyKey

    @field_validator("first_due_at")
    @classmethod
    def due_timestamp_must_be_aware(cls, value):
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Timezone-aware timestamp required")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def schedule_intervals_and_due_values_must_match(self):
        if self.interval_days is None and self.interval_meter is None:
            raise ValueError("At least one preventive interval is required")
        if (self.interval_days is None) != (self.first_due_at is None):
            raise ValueError("first_due_at is required exactly when interval_days is set")
        if (self.interval_meter is None) != (self.first_due_meter is None):
            raise ValueError("first_due_meter is required exactly when interval_meter is set")
        return self
