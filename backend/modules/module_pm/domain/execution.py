"""Execution input contracts: work orders, consumptions. Quantity events are service-managed."""
from datetime import date, datetime, time
from decimal import Decimal
from typing import Annotated, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

Code = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
Amount = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=6, allow_inf_nan=False)]
Currency = Annotated[str, StringConstraints(pattern=r'^[A-Z]{3,10}$')]


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid')


class WorkOrder(Input):
    # The API accepts a missing/display-only code; the service always generates
    # the authoritative business key from the project's persisted orders.
    work_order_code: Optional[Code] = None
    activity_id: UUID
    assignee_user_id: Optional[UUID] = None
    issue_date: Optional[datetime] = None
    planned_start_date: Optional[datetime] = None
    notes: str = ''

    @field_validator('issue_date', 'planned_start_date', mode='before')
    @classmethod
    def normalize_legacy_planned_start_date(cls, value):
        """Keep date-only API clients valid while persisting a planned moment."""
        if isinstance(value, date) and not isinstance(value, datetime):
            return datetime.combine(value, time.min)
        if isinstance(value, str) and len(value) == 10:
            return f'{value}T00:00:00'
        return value


class WorkOrderUpdate(Input):
    assignee_user_id: Optional[UUID] = None
    issue_date: Optional[datetime] = None
    planned_start_date: Optional[datetime] = None
    notes: str = ''

    @field_validator('issue_date', 'planned_start_date', mode='before')
    @classmethod
    def normalize_legacy_planned_start_date(cls, value):
        if isinstance(value, date) and not isinstance(value, datetime):
            return datetime.combine(value, time.min)
        if isinstance(value, str) and len(value) == 10:
            return f'{value}T00:00:00'
        return value


class WorkOrderDecision(Input):
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class Consumption(Input):
    consumption_code: Optional[Code] = None
    work_order_id: UUID
    item_name: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    item_type: str = ''
    quantity: Amount
    unit: str = ''
    unit_price: Amount
    currency: Currency
    rate_date: date
    reference: str = ''


class QuantityUpdate(Input):
    quantity: Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=6, allow_inf_nan=False)]
    notes: str = ''


class StatusChange(BaseModel):
    model_config = ConfigDict(extra='forbid')
    status: str


KINDS = {
    'work_orders': ('pm_work_orders', WorkOrder, 'work_order_code'),
    'consumptions': ('pm_work_order_consumptions', Consumption, 'consumption_code'),
}
