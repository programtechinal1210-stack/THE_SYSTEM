from datetime import date
from uuid import UUID
from pydantic import BaseModel, ConfigDict, model_validator


class ReportFilters(BaseModel):
    model_config=ConfigDict(extra='forbid')
    date_from: date | None = None
    date_to: date | None = None
    phase_id: UUID | None = None
    task_id: UUID | None = None
    activity_id: UUID | None = None
    status: str | None = None

    @model_validator(mode='after')
    def dates(self):
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError('Start date must not follow end date')
        return self
