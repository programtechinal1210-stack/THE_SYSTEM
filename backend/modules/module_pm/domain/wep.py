"""Weekly Execution Plan (WEP) input contracts."""
from datetime import date
from decimal import Decimal
from typing import Annotated, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Code = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
Amount = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=6, allow_inf_nan=False)]


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid')


class WeeklyPlan(Input):
    week_code: Code
    start_date: date
    end_date: date

    @model_validator(mode='after')
    def valid_dates(self):
        if self.end_date < self.start_date:
            raise ValueError('End date must not precede start date')
        return self


class WeeklyPlanItem(Input):
    activity_id: UUID
    weekly_target: Amount
    assignee_user_id: Optional[UUID] = None


class WeeklyCommitmentUpdate(Input):
    weekly_target: Amount
    assignee_user_id: Optional[UUID] = None


class StatusChange(BaseModel):
    model_config = ConfigDict(extra='forbid')
    status: str
    reason: str = Field(default='', max_length=2000)


class Carryover(BaseModel):
    model_config = ConfigDict(extra='forbid')
    next_week_code: Code
    next_start_date: date
    next_end_date: date

    @model_validator(mode='after')
    def valid_dates(self):
        if self.next_end_date < self.next_start_date:
            raise ValueError('End date must not precede start date')
        return self
