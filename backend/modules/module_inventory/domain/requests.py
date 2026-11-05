from datetime import datetime, timezone
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator
from .financial_policy import quantity


class RequestLine(BaseModel):
    model_config = ConfigDict(extra='forbid')
    item_id: UUID
    quantity: str = Field(max_length=40)

    @field_validator('quantity')
    @classmethod
    def valid_quantity(cls, value):
        quantity(value)
        return value


class MaterialRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    organization_id: UUID
    department_id: UUID | None = None
    request_no: str | None = Field(default=None, min_length=1, max_length=80)
    lines: list[RequestLine] = Field(min_length=1, max_length=100)


class Decision(BaseModel):
    model_config = ConfigDict(extra='forbid')
    reason: str = Field(default='', max_length=2000)
    # Missing means approve every requested quantity; explicit values use base units.
    approved_quantities: dict[UUID, str] | None = None


class Reservation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_line_id: UUID
    warehouse_id: UUID
    location_id: UUID | None = None
    quantity: str = Field(max_length=40)
    reservation_key: str = Field(min_length=1, max_length=120)
    expires_at: datetime | None = None

    @field_validator('quantity')
    @classmethod
    def valid_quantity(cls, value):
        quantity(value)
        return value

    @field_validator('expires_at')
    @classmethod
    def aware_expiry(cls, value):
        if value is not None:
            if value.tzinfo is None:
                raise ValueError('Expiry requires timezone')
            value = value.astimezone(timezone.utc)
        return value
