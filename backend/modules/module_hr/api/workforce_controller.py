from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from infrastructure.database.db_context import get_session
from ..application.workforce_service import WorkforceService


router = APIRouter(prefix="/api/v1/hr", tags=["human-resources"])
Session = Depends(get_session, scope="function")


class FieldTaskCreate(BaseModel):
    organization_id: UUID | None = None
    task_no: str = Field(min_length=1, max_length=40)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="")
    owner_unit_id: UUID
    business_date: date
    planned_start_at: str | None = None
    planned_end_at: str | None = None
    location_text: str = Field(default="", max_length=200)


class WorkforceRequestCreate(BaseModel):
    organization_id: UUID | None = None
    request_no: str = Field(min_length=1, max_length=40)
    requesting_unit_id: UUID
    task_id: UUID | None = None
    requested_position: str = Field(default="", max_length=150)
    headcount: int = Field(ge=1)
    start_at: str
    end_at: str
    priority: str = "normal"
    purpose: str = Field(min_length=1)


class AssignmentCreate(BaseModel):
    organization_id: UUID | None = None
    employee_id: UUID
    task_id: UUID | None = None
    request_id: UUID | None = None
    beneficiary_unit_id: UUID
    assignment_kind: str
    exclusivity: str = "exclusive"
    business_date: date
    start_at: str | None = None
    end_at: str | None = None
    status: str = "pending"
    notes: str = ""


class WorkflowTransition(BaseModel):
    row_version: int = Field(ge=1)
    action: str
    reason: str = Field(default="", max_length=2000)


def svc(session, request):
    return WorkforceService(session, request)


def ids(data, *names):
    for name in names:
        if data.get(name) is not None:
            data[name] = UUID(data[name]).hex
    return data


@router.get("/field-tasks")
async def tasks(request: Request, employee_id: UUID | None = None, q: str | None = None,
                status: str | None = None, business_date_from: date | None = None,
                business_date_to: date | None = None, unit_id: UUID | None = None,
                page: int = 1, page_size: int = 10, session=Session):
    return await svc(session, request).list_rows(
        "hr_field_tasks", employee_id.hex if employee_id else None,
        {"q": q, "status": status, "business_date_from": str(business_date_from) if business_date_from else None,
         "business_date_to": str(business_date_to) if business_date_to else None,
         "unit_id": unit_id.hex if unit_id else None, "page": page, "page_size": page_size}
    )


@router.post("/field-tasks", status_code=201)
async def create_task(payload: FieldTaskCreate, request: Request, session=Session):
    data = ids(payload.model_dump(mode="json"), "organization_id", "owner_unit_id")
    data["business_date"] = str(data["business_date"])
    return await svc(session, request).create_task(data)

@router.post("/field-tasks/{task_id}/transition")
async def transition_task(task_id: UUID, payload: WorkflowTransition,
                          request: Request, session=Session):
    return await svc(session, request).transition_task(task_id.hex, payload.model_dump())

@router.get("/workforce-requests")
async def requests(request: Request, q: str | None = None, status: str | None = None,
                   business_date_from: date | None = None, business_date_to: date | None = None,
                   unit_id: UUID | None = None, session=Session):
    return await svc(session, request).list_rows(
        "hr_workforce_requests", filters={
            "q": q, "status": status,
            "business_date_from": str(business_date_from) if business_date_from else None,
            "business_date_to": str(business_date_to) if business_date_to else None,
            "unit_id": unit_id.hex if unit_id else None,
        }
    )

@router.get("/workforce-requests/coverage")
async def request_coverages(request: Request, session=Session):
    return await svc(session, request).list_coverage()

@router.post("/workforce-requests", status_code=201)
async def create_request(payload: WorkforceRequestCreate, request: Request, session=Session):
    data = ids(payload.model_dump(mode="json"), "organization_id", "requesting_unit_id", "task_id")
    return await svc(session, request).create_request(data)

@router.post("/workforce-requests/{request_id}/transition")
async def transition_request(request_id: UUID, payload: WorkflowTransition,
                             request: Request, session=Session):
    return await svc(session, request).transition_request(request_id.hex, payload.model_dump())


@router.get("/workforce-requests/{request_id}/coverage")
async def coverage(request_id: UUID, request: Request, session=Session):
    return await svc(session, request).request_coverage(request_id.hex)


@router.get("/assignments")
async def assignments(request: Request, employee_id: UUID | None = None, session=Session):
    return await svc(session, request).list_rows("hr_assignments", employee_id.hex if employee_id else None)


@router.post("/assignments", status_code=201)
async def create_assignment(payload: AssignmentCreate, request: Request, session=Session):
    data = ids(payload.model_dump(mode="json"), "organization_id", "employee_id", "task_id", "request_id", "beneficiary_unit_id")
    data["business_date"] = str(data["business_date"])
    return await svc(session, request).create_assignment(data)

@router.post("/assignments/{assignment_id}/transition")
async def transition_assignment(assignment_id: UUID, payload: WorkflowTransition,
                                request: Request, session=Session):
    return await svc(session, request).transition_assignment(assignment_id.hex, payload.model_dump())
