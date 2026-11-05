from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from pydantic import StringConstraints

from infrastructure.database.db_context import get_session
from ..application.operator_qualification_service import OperatorQualificationService


router = APIRouter(prefix="/api/v1/hr", tags=["human-resources-operator-qualifications"])
Session = Depends(get_session, scope="function")


class QualificationCreate(BaseModel):
    equipment_class_code: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
    qualification_code: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
    credential_reference: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    issuer_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    evidence_reference: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
    valid_from: date
    valid_until: date | None = None
    idempotency_key: str = Field(min_length=1, max_length=120)


class QualificationDecision(BaseModel):
    decision_reason: str = Field(default="", max_length=2000)
    authority_ref: str = Field(default="", max_length=200)


@router.get("/employees/{employee_id}/operator-qualifications")
async def list_operator_qualifications(employee_id: UUID, request: Request, session=Session):
    return await OperatorQualificationService(session, request).list_for_employee(employee_id.hex)


@router.post("/employees/{employee_id}/operator-qualifications", status_code=201)
async def create_operator_qualification(
    employee_id: UUID, payload: QualificationCreate, request: Request, session=Session
):
    return await OperatorQualificationService(session, request).create(employee_id.hex, payload)


@router.post("/operator-qualifications/{qualification_id}/{action}")
async def decide_operator_qualification(
    qualification_id: UUID,
    action: str,
    payload: QualificationDecision,
    request: Request,
    session=Session,
):
    return await OperatorQualificationService(session, request).decide(
        qualification_id.hex, action, payload.decision_reason, payload.authority_ref
    )


@router.get("/operator-qualifications/eligibility")
async def operator_qualification_eligibility(
    employee_id: UUID,
    request: Request,
    equipment_class_code: str = Query(min_length=1, max_length=50),
    at_date: date | None = None,
    session=Session,
):
    from core.access import require
    from ..application.employee_service import EmployeeService
    require(request, "hr.operator_qualifications.view")
    employee_service = EmployeeService(session, request)
    organization_id = employee_service._organization(permission="hr.operator_qualifications.view")
    await employee_service._employee(
        employee_id.hex, organization_id, "hr.operator_qualifications.view"
    )
    return await OperatorQualificationService.eligibility(
        session, employee_id.hex, organization_id, equipment_class_code, at_date
    )
