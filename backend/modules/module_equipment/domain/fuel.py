"""Input contracts for operational fuel and energy events."""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, StringConstraints, field_validator, model_validator

from .catalog import Input

EnergyType = Literal["diesel", "gasoline", "electricity", "other"]
FuelEventType = Literal["opening", "issued", "consumed", "returned", "adjustment_in", "adjustment_out"]
FuelUnit = Literal["L", "kWh", "kg", "m3"]
IdempotencyKey = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class FuelEventInput(Input):
    event_type: FuelEventType
    energy_type: EnergyType
    quantity: Decimal = Field(gt=0, max_digits=20, decimal_places=6)
    unit: FuelUnit
    event_at: datetime | None = None
    related_issue_event_id: UUID | None = None
    unit_cost: Decimal | None = Field(default=None, ge=0, max_digits=20, decimal_places=6)
    currency_id: str | None = Field(default=None, min_length=32, max_length=36)
    reason_code: Reason | None = None
    notes: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] = ""
    idempotency_key: IdempotencyKey

    @field_validator("event_at")
    @classmethod
    def event_time_must_be_aware(cls, value):
        if value is not None:
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("Timezone-aware timestamp required")
            return value.astimezone(timezone.utc)
        return value

    @field_validator("currency_id")
    @classmethod
    def currency_id_must_be_uuid(cls, value):
        if value is None:
            return value
        from uuid import UUID

        return UUID(value).hex

    @model_validator(mode="after")
    def price_fields_must_match(self):
        if (self.unit_cost is None) != (self.currency_id is None):
            raise ValueError("unit_cost and currency_id must be supplied together")
        if self.event_type in ("adjustment_in", "adjustment_out") and not self.reason_code:
            raise ValueError("fuel balance adjustments require a reason_code")
        if self.related_issue_event_id is not None and self.event_type != "returned":
            raise ValueError("Only a returned fuel event can reference an issued fuel event")
        return self


class FuelEventDecisionInput(Input):
    decision_reason: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] = ""
