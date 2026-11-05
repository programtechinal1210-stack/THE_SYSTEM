from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CreateScheduleVersion(BaseModel):
    model_config = ConfigDict(extra='forbid')
    baseline_id: UUID
    reason: str | None = Field(default=None, max_length=500)

    @field_validator('reason')
    @classmethod
    def normalize_reason(cls, value):
        return value.strip() if value else None


class RecalculateForecast(BaseModel):
    """Explicit request to calculate a draft from the existing Actual contract."""
    model_config = ConfigDict(extra='forbid')
    baseline_id: UUID
    actual_as_of: datetime
    reason: str | None = Field(default=None, max_length=500)

    @field_validator('reason')
    @classmethod
    def normalize_reason(cls, value):
        return value.strip() if value else None


class ApproveScheduleVersion(BaseModel):
    """Decision context is mandatory only for a partial/blocked schedule."""
    model_config = ConfigDict(extra='forbid')
    reason: str | None = Field(default=None, max_length=500)

    @field_validator('reason')
    @classmethod
    def normalize_reason(cls, value):
        return value.strip() or None if value else None


class RejectScheduleVersion(BaseModel):
    model_config = ConfigDict(extra='forbid')
    reason: str = Field(min_length=1, max_length=500)

    @field_validator('reason')
    @classmethod
    def normalize_reason(cls, value):
        value = value.strip()
        if not value:
            raise ValueError('reason must not be blank')
        return value
