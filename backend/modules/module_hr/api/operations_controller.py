import csv
import io
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from starlette.responses import StreamingResponse

from infrastructure.database.db_context import get_session
from ..application.operations_service import HROperationsService


router = APIRouter(prefix="/api/v1/hr", tags=["human-resources"])
Session = Depends(get_session, scope="function")


class ShiftTemplateInput(BaseModel):
    organization_id: UUID | None = None
    code: str = Field(min_length=1, max_length=30)
    name_ar: str = Field(min_length=1, max_length=100)
    start_local_time: str
    end_local_time: str
    end_day_offset: int = Field(ge=0, le=1)
    break_minutes: int = Field(default=0, ge=0)
    timezone_name: str = Field(min_length=1, max_length=80)


class ShiftRosterInput(BaseModel):
    organization_id: UUID | None = None
    employee_id: UUID
    shift_template_id: UUID | None = None
    owner_unit_id: UUID
    work_unit_id: UUID
    business_date: date
    start_at: str | None = None
    end_at: str | None = None
    planned_break_minutes: int = Field(default=0, ge=0)
    timezone_name: str = "UTC"
    shift_name_snapshot: str = ""
    start_fold: int | None = Field(default=None, ge=0, le=1)
    end_fold: int | None = Field(default=None, ge=0, le=1)
    location_text: str = Field(default="", max_length=200)
    notes: str = ""


class AttendanceInput(BaseModel):
    organization_id: UUID | None = None
    employee_id: UUID
    attendance_kind: str
    shift_roster_id: UUID | None = None
    assignment_id: UUID | None = None
    task_id: UUID | None = None
    root_attendance_id: UUID | None = None
    business_date: date
    status: str
    approval_status: str = "draft"
    source: str = "manual"
    source_system: str | None = None
    source_record_id: str | None = None
    check_in_at: str | None = None
    check_out_at: str | None = None
    notes: str = ""


class AttendanceApproval(BaseModel):
    row_version: int = Field(ge=1)

class AttendanceSubmission(BaseModel):
    row_version: int = Field(ge=1)

class AttendanceRejection(BaseModel):
    row_version: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=2000)


class AttendanceCorrection(BaseModel):
    row_version: int = Field(ge=1)
    status: str
    reason: str = Field(min_length=1, max_length=2000)


class IssueInput(BaseModel):
    organization_id: UUID | None = None
    employee_id: UUID | None = None
    attendance_id: UUID | None = None
    task_id: UUID | None = None
    issue_type: str
    business_date: date
    priority: str = "normal"
    excuse_decision: str = "not_applicable"
    reason: str = Field(min_length=1)
    proposed_solution: str = ""
    responsible_unit_id: UUID | None = None
    responsible_employee_id: UUID | None = None


class IssueTransition(BaseModel):
    row_version: int = Field(ge=1)
    action: str
    resolution_notes: str = ""


def _ids(data, *fields):
    for field in fields:
        if data.get(field) is not None:
            data[field] = UUID(data[field]).hex
    if data.get("business_date") is not None:
        data["business_date"] = str(data["business_date"])
    return data


def _service(session, request):
    return HROperationsService(session, request)


@router.get("/shift-templates")
async def list_shift_templates(request: Request, session=Session):
    return await _service(session, request).list_templates()


@router.post("/shift-templates", status_code=201)
async def create_shift_template(payload: ShiftTemplateInput, request: Request, session=Session):
    data = _ids(payload.model_dump(mode="json"), "organization_id")
    return await _service(session, request).create_template(data)


@router.get("/shift-roster")
async def list_shift_roster(request: Request, employee_id: UUID | None = None, session=Session):
    return await _service(session, request).list_roster(employee_id.hex if employee_id else None)


@router.post("/shift-roster", status_code=201)
async def create_shift_roster(payload: ShiftRosterInput, request: Request, session=Session):
    data = _ids(payload.model_dump(mode="json"), "organization_id", "employee_id",
                "shift_template_id", "owner_unit_id", "work_unit_id")
    return await _service(session, request).create_roster(data)


@router.post("/shift-roster/{roster_id}/confirm")
async def confirm_shift_roster(roster_id: UUID, request: Request, session=Session):
    return await _service(session, request).confirm_roster(roster_id.hex)


@router.get("/attendance")
async def list_attendance(request: Request, business_date: date | None = None,
                         employee_id: UUID | None = None, session=Session):
    return await _service(session, request).list_attendance(
        str(business_date) if business_date else None, employee_id.hex if employee_id else None)


@router.post("/attendance", status_code=201)
async def create_attendance(payload: AttendanceInput, request: Request, session=Session):
    data = _ids(payload.model_dump(mode="json"), "organization_id", "employee_id",
                "shift_roster_id", "assignment_id", "task_id", "root_attendance_id")
    return await _service(session, request).create_attendance(data)


@router.post("/attendance/{attendance_id}/approve")
async def approve_attendance(attendance_id: UUID, payload: AttendanceApproval,
                             request: Request, session=Session):
    return await _service(session, request).approve_attendance(attendance_id.hex, payload.row_version)

@router.post("/attendance/{attendance_id}/submit")
async def submit_attendance(attendance_id: UUID, payload: AttendanceSubmission,
                            request: Request, session=Session):
    return await _service(session, request).submit_attendance(attendance_id.hex, payload.row_version)

@router.post("/attendance/{attendance_id}/reject")
async def reject_attendance(attendance_id: UUID, payload: AttendanceRejection,
                            request: Request, session=Session):
    return await _service(session, request).reject_attendance(
        attendance_id.hex, payload.row_version, payload.reason)


@router.post("/attendance/{attendance_id}/correct", status_code=201)
async def correct_attendance(attendance_id: UUID, payload: AttendanceCorrection,
                             request: Request, session=Session):
    return await _service(session, request).correct_attendance(
        attendance_id.hex, payload.model_dump())


@router.get("/issues")
async def list_issues(request: Request, employee_id: UUID | None = None, session=Session):
    return await _service(session, request).list_issues(employee_id.hex if employee_id else None)


@router.post("/issues", status_code=201)
async def create_issue(payload: IssueInput, request: Request, session=Session):
    data = _ids(payload.model_dump(mode="json"), "organization_id", "employee_id",
                "attendance_id", "task_id", "responsible_unit_id", "responsible_employee_id")
    return await _service(session, request).create_issue(data)


@router.post("/issues/{issue_id}/transition")
async def transition_issue(issue_id: UUID, payload: IssueTransition,
                           request: Request, session=Session):
    return await _service(session, request).transition_issue(issue_id.hex, payload.model_dump())


@router.get("/reports/{report_code}")
async def get_report(report_code: str, request: Request, start_date: date | None = None,
                     end_date: date | None = None, session=Session):
    return await _service(session, request).report(
        report_code, str(start_date) if start_date else None, str(end_date) if end_date else None)


@router.get("/reports/{report_code}/export")
async def export_report(report_code: str, request: Request, start_date: date | None = None,
                        end_date: date | None = None, session=Session):
    from core.access import require

    require(request, "hr.report.export")
    report = await _service(session, request).report(
        report_code, str(start_date) if start_date else None, str(end_date) if end_date else None,
        extra_permission="hr.report.export")
    output = io.StringIO()
    rows = report["items"]
    if rows:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    request.state.audit_details = {
        "entity_type": "hr.report", "entity_id": None,
        "new": {"report": report_code, "row_count": len(rows)},
        "summary": "HR report exported",
    }
    output.seek(0)
    return StreamingResponse(output, media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": f'attachment; filename="hr-{report_code}.csv"'})
