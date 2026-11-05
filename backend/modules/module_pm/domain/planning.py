"""Planning input contracts; execution fields are deliberately not writable."""
from datetime import date
from decimal import Decimal, localcontext, ROUND_HALF_EVEN
from typing import Annotated, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Code = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
Amount = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=6, allow_inf_nan=False)]


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Project(Input):
    client_name: Annotated[str, StringConstraints(strip_whitespace=True,max_length=200)] = ''
    project_code: Code = ''
    name: Name
    organization_id: UUID
    project_manager_user_id: UUID
    currency: Annotated[str, StringConstraints(pattern=r'^[A-Z]{3,10}$')]
    directive_date: date
    start_date: date
    daily_hours: Annotated[Decimal, Field(gt=0, le=24, decimal_places=2)] = Decimal('8')


class Phase(Input):
    phase_code: Code = ''
    name: Name
    owner_user_id: UUID | None = None


class Task(Input):
    phase_id: UUID
    task_code: Code = ''
    name: Name
    owner_user_id: UUID | None = None


class Activity(Input):
    priority: Literal['low','normal','high','urgent'] = 'normal'
    task_id: UUID
    activity_code: Code = ''
    name: Name
    planned_quantity: Amount = Decimal('0')
    planned_duration: Amount = Decimal('0')
    unit: Annotated[str, StringConstraints(max_length=40)] = ''
    currency: Annotated[str, StringConstraints(pattern=r'^[A-Z]{3,10}$')]
    rate_date: date
    description: Annotated[str, StringConstraints(max_length=4000)] = ''
    notes: Annotated[str, StringConstraints(max_length=4000)] = ''
    attachment_url: Annotated[str, StringConstraints(max_length=2000, pattern=r'^(https?://\S+)?$')] = ''
    planned_start_date: date | None = None
    planned_end_date: date | None = None

    @model_validator(mode='after')
    def ordered_dates(self):
        if self.planned_start_date and self.planned_end_date and self.planned_end_date < self.planned_start_date:
            raise ValueError('Planned finish must not precede start')
        return self


class Requirement(Input):
    activity_id: UUID
    requirement_code: Code = ''
    name: Name
    resource_type: Annotated[str, StringConstraints(max_length=80)] = ''
    specifications: Annotated[str, StringConstraints(max_length=2000)] = ''
    unit: Annotated[str, StringConstraints(max_length=40)] = ''
    quantity: Amount
    unit_price: Amount
    currency: Annotated[str, StringConstraints(pattern=r'^[A-Z]{3,10}$')]
    rate_date: date
    productivity: Amount = Decimal('0')
    source: Annotated[str, StringConstraints(max_length=500)] = ''
    item_category: Annotated[str, StringConstraints(max_length=200)] = ''
    notes: Annotated[str, StringConstraints(max_length=4000)] = ''


KINDS = {
    'projects': ('pm_projects', Project, 'project_code', None, None),
    'phases': ('pm_phases', Phase, 'phase_code', 'projects', 'project_id'),
    'tasks': ('pm_tasks', Task, 'task_code', 'phases', 'phase_id'),
    'activities': ('pm_activities', Activity, 'activity_code', 'tasks', 'task_id'),
    'requirements': ('pm_activity_resource_requirements', Requirement, 'requirement_code', 'activities', 'activity_id'),
}


def cost(quantity, price, rate):
    with localcontext() as ctx:
        ctx.prec = 120
        return Decimal(quantity) * Decimal(price) * Decimal(rate)


def total(values):
    with localcontext() as ctx:
        ctx.prec = 120
        return sum((Decimal(v) for v in values), Decimal(0)).quantize(Decimal('.01'), rounding=ROUND_HALF_EVEN)


def in_scope(project, actor, admin, scopes):
    return bool(admin or 'institution' in scopes
                or ('organization' in scopes and project['organization_id'] == getattr(actor.organization_id, 'hex', None))
                or ('self' in scopes and project['project_manager_user_id'] == actor.id.hex))
