"""Governance/control input contracts. No execution/actual fields are writable here."""
from datetime import date
from decimal import Decimal
from typing import Annotated, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Code = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
Amount = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=6, allow_inf_nan=False)]
Level = Annotated[str, StringConstraints(pattern=r'^(project|phase|task|activity)$')]
Currency = Annotated[str, StringConstraints(pattern=r'^[A-Z]{3,10}$')]


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Risk(Input):
    risk_code: Code
    level: Level = 'project'
    phase_id: Optional[UUID] = None
    task_id: Optional[UUID] = None
    activity_id: Optional[UUID] = None
    description: Annotated[str, StringConstraints(min_length=1, max_length=2000)]
    classification: str = ''
    owner_user_id: Optional[UUID] = None
    probability: Annotated[Decimal, Field(ge=0, le=100, max_digits=18, decimal_places=6, allow_inf_nan=False)] = Decimal('0')
    impact: int = Field(default=1, ge=1, le=5)
    corrective_action: str = ''
    discovery_date: Optional[date] = None

    @model_validator(mode='after')
    def linked_entity_matches_level(self):
        required = {'project': None, 'phase': 'phase_id', 'task': 'task_id', 'activity': 'activity_id'}[self.level]
        if required is None:
            if any((self.phase_id, self.task_id, self.activity_id)):
                raise ValueError('Project-level risks cannot reference a WBS item')
            return self
        if getattr(self, required) is None:
            raise ValueError('The selected risk level requires its linked project item')
        disallowed = {
            'phase': (self.task_id, self.activity_id),
            'task': (self.activity_id,),
            'activity': (),
        }[self.level]
        if any(disallowed):
            raise ValueError('Risk links must match the selected hierarchy level')
        return self


class Deviation(Input):
    deviation_code: Code
    level: Level = 'project'
    phase_id: Optional[UUID] = None
    task_id: Optional[UUID] = None
    activity_id: Optional[UUID] = None
    deviation_type: str = ''
    description: str = ''
    causes: str = ''
    impact: int = Field(default=3, ge=1, le=5)
    corrective_action: str = ''
    responsible_user_id: Optional[UUID] = None
    target_date: Optional[date] = None


class CashFlowItem(Input):
    item_code: Code
    cash_flow_type: Annotated[str, StringConstraints(pattern=r'^(inflow|outflow)$')] = 'outflow'
    amount: Amount
    currency: Currency
    period: str
    rate_date: date
    notes: str = ''


class CommunicationItem(Input):
    item_code: Code
    report_type: str = ''
    purpose: str = ''
    frequency: str = ''
    sender_user_id: Optional[UUID] = None
    receivers: str = ''
    mechanism: str = ''
    notes: str = ''


class DailyReport(Input):
    report_code: Code
    report_date: date
    activities_count: int = Field(default=0, ge=0)
    planned_volume: Amount = Decimal('0')
    executed_volume: Amount = Decimal('0')
    daily_cost: Amount = Decimal('0')
    actual_workers: int = Field(default=0, ge=0)
    work_hours: Amount = Decimal('0')
    equipment_used: str = ''
    materials_used: str = ''
    problems: str = ''
    notes: str = ''


# table, model, code column
CONTROL_KINDS = {
    'risks': ('pm_risks', Risk, 'risk_code'),
    'deviations': ('pm_deviations', Deviation, 'deviation_code'),
    'cashflows': ('pm_cash_flow_items', CashFlowItem, 'item_code'),
    'communications': ('pm_communication_plan_items', CommunicationItem, 'item_code'),
    'reports': ('pm_daily_reports', DailyReport, 'report_code'),
}


class StatusChange(BaseModel):
    model_config = ConfigDict(extra='forbid')
    status: str
