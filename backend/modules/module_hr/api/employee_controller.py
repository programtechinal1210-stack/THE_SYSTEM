from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from infrastructure.database.db_context import get_session
from ..application.employee_service import EmployeeService


router = APIRouter(prefix="/api/v1/hr", tags=["human-resources"])
Session = Depends(get_session, scope="function")


class EmployeeCreate(BaseModel):
    organization_id: UUID | None = None
    employee_no: str = Field(min_length=1, max_length=30)
    full_name: str = Field(min_length=1, max_length=200)
    phone: str = Field(default="", max_length=50)
    home_unit_id: UUID
    position_title: str = Field(default="", max_length=150)
    hire_date: str | None = None


class DecisionCreate(BaseModel):
    change_type: str
    effective_date: str
    to_unit_id: UUID | None = None
    to_position_title: str = Field(default="", max_length=150)
    reference_no: str = Field(default="", max_length=80)
    supersedes_record_id: UUID | None = None
    supersedes_row_version: int | None = Field(default=None, ge=1)
    reason: str = Field(default="", max_length=2000)
    notes: str = Field(default="", max_length=4000)


def service(session, request):
    return EmployeeService(session, request)


@router.get("/")
async def overview(request: Request, session=Session):
    svc = service(session, request)
    return {"version": "0.1.0", "status": "ready", "self_service": False,
            "employees": await svc.list_employees()}


@router.get("/employees")
async def list_employees(
    request: Request,
    q: str | None = Query(default=None, max_length=120),
    unit_id: UUID | None = None,
    position_title: str | None = Query(default=None, max_length=150),
    employment_status: str | None = Query(default=None, max_length=30),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session=Session,
):
    return await service(session, request).list_employees(
        q=q, unit_id=unit_id.hex if unit_id else None,
        position_title=position_title, employment_status=employment_status,
        page=page, page_size=page_size,
    )


@router.post("/employees", status_code=201)
async def create_employee(payload: EmployeeCreate, request: Request, session=Session):
    data = payload.model_dump(mode="json")
    if data["organization_id"] is not None: data["organization_id"] = UUID(data["organization_id"]).hex
    data["home_unit_id"] = UUID(data["home_unit_id"]).hex
    return await service(session, request).create_employee(data)


@router.get("/employees/{employee_id}")
async def employee(employee_id: UUID, request: Request, session=Session):
    return await service(session, request).get_employee(employee_id.hex)


@router.get("/employees/{employee_id}/employment-records")
async def history(employee_id: UUID, request: Request, as_of: date | None = None, session=Session):
    return await service(session, request).history(employee_id.hex, as_of.isoformat() if as_of else None)


@router.get("/employment-records")
async def list_decisions(
    request: Request,
    q: str | None = Query(default=None, max_length=120),
    change_type: str | None = Query(default=None, max_length=40),
    status: str | None = Query(default=None, max_length=30),
    unit_id: UUID | None = None,
    effective_from: date | None = None,
    effective_to: date | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session=Session,
):
    return await service(session, request).list_decisions(
        q=q, change_type=change_type, status=status,
        unit_id=unit_id.hex if unit_id else None,
        effective_from=effective_from.isoformat() if effective_from else None,
        effective_to=effective_to.isoformat() if effective_to else None,
        page=page, page_size=page_size,
    )


@router.get("/employment-records/{record_id}")
async def decision(record_id: UUID, request: Request, session=Session):
    return await service(session, request).decision(record_id.hex)


@router.post("/employees/{employee_id}/employment-records", status_code=201)
async def create_decision(employee_id: UUID, payload: DecisionCreate, request: Request, session=Session):
    data = payload.model_dump(mode="json")
    for key in ("to_unit_id", "supersedes_record_id"):
        if data[key] is not None: data[key] = UUID(data[key]).hex
    return await service(session, request).create_decision(employee_id.hex, data)
