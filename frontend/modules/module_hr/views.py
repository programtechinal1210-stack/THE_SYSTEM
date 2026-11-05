from datetime import date, timedelta

from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from uuid import UUID

from shared.services.api_client import (
    ApiClient,
    ApiException,
    ForbiddenException,
    UnauthorizedException,
)


SCREENS = {
    "reports": ("التقارير والمؤشرات التشغيلية", "hr.report.view"),
    "employees": ("الموظفون", "hr.employees.view"),
    "decisions": ("القرارات الإدارية", "hr.employment_records.view"),
    "workforce": ("المهام والتوزيع", "hr.workforce.view"),
    "shifts": ("الورديات والحضور", "hr.shift.view"),
    "issues": ("المشكلات والتقارير", "hr.issue.view"),
}

NAVIGATION = (
    ("dashboard", "لوحة القوى العاملة", "hr.employees.view"),
    ("reports", "التقارير والمؤشرات", "hr.report.view"),
    ("employees", "الموظفون", "hr.employees.view"),
    ("decisions", "القرارات الإدارية", "hr.employment_records.view"),
    ("workforce", "المهام والتوزيع", "hr.workforce.view"),
    ("shifts", "الورديات والحضور", "hr.shift.view"),
    ("issues", "المشكلات والتقارير", "hr.issue.view"),
)

DASHBOARD_PERMISSIONS = (
    "hr.employees.view",
    "hr.workforce.view",
    "hr.task.view",
    "hr.shift.view",
    "hr.attendance.view",
    "hr.issue.view",
    "hr.report.view",
)

ACTION_PERMISSIONS = {
    "employee_create": "hr.employees.create",
    "decision_create": "hr.employment_records.manage",
    "task_create": "hr.task.manage",
    "task_transition": "hr.task.manage",
    "request_create": "hr.workforce.request",
    "request_transition": "hr.workforce.request",
    "request_approve": "hr.workforce.approve",
    "assignment_create": "hr.assignment.manage",
    "assignment_approve": "hr.assignment.approve",
    "template_create": "hr.shift.manage",
    "roster_create": "hr.shift.manage",
    "attendance_create": "hr.attendance.record",
    "attendance_submit": "hr.attendance.record",
    "attendance_approve": "hr.attendance.approve",
    "attendance_reject": "hr.attendance.approve",
    "attendance_correct": "hr.attendance.correct",
    "issue_create": "hr.issue.manage",
    "issue_transition": "hr.issue.manage",
    "report_export": "hr.report.export",
}


def _allowed(identity, permission):
    return identity.get("is_admin", False) or permission in identity.get("permissions", [])


def _can_view_dashboard(identity):
    return any(_allowed(identity, permission) for permission in DASHBOARD_PERMISSIONS)


def _allowed_any(identity, *permissions):
    return any(_allowed(identity, permission) for permission in permissions)


def _can_view_section(identity, section):
    if section == "dashboard":
        return _can_view_dashboard(identity)
    if section == "issues":
        return _allowed_any(identity, "hr.issue.view", "hr.report.view")
    if section == "reports":
        return _allowed(identity, "hr.report.view")
    if section == "workforce":
        return _allowed_any(identity, "hr.workforce.view", "hr.task.view")
    if section == "shifts":
        return _allowed_any(identity, "hr.shift.view", "hr.attendance.view")
    return _allowed(identity, dict(SCREENS)[section][1])


DECISION_TYPE_LABELS = {
    "hire": "تعيين", "transfer": "نقل", "position_change": "تغيير وظيفة",
    "suspension": "إيقاف", "termination": "إنهاء خدمة", "reinstatement": "إعادة تفعيل",
}
DECISION_STATUS_LABELS = {
    "approved": "معتمد", "rejected": "مرفوض", "cancelled": "ملغى",
    "draft": "مسودة", "pending": "قيد المراجعة",
}


def _decision_snapshot(client, request):
    params = {
        "q": request.GET.get("q", "").strip(),
        "change_type": request.GET.get("change_type", "").strip(),
        "status": request.GET.get("status", "").strip(),
        "unit_id": request.GET.get("unit_id", "").strip(),
        "effective_from": request.GET.get("effective_from", "").strip(),
        "effective_to": request.GET.get("effective_to", "").strip(),
        "page": request.GET.get("page", "1"),
        "page_size": request.GET.get("page_size", "10"),
    }
    params = {key: value for key, value in params.items() if value}
    try:
        response = client.get("/hr/employment-records", params=params)
    except (ForbiddenException, ApiException):
        return {"available": False, "items": [], "summary": None, "filters": params}
    if isinstance(response, list):
        response = {"items": response, "total": len(response), "page": 1, "pages": 1, "page_size": len(response)}
    response = response if isinstance(response, dict) else {}
    for row in response.get("items", []):
        row["change_type_label"] = DECISION_TYPE_LABELS.get(row.get("change_type"), row.get("change_type") or "غير متاح")
        row["status_label"] = DECISION_STATUS_LABELS.get(row.get("status"), row.get("status") or "غير متاح")
        row["is_future"] = row.get("status") == "approved" and row.get("effective_date", "") > timezone.localdate().isoformat()
        row["effective_label"] = "مستقبلي" if row["is_future"] else "ساري زمنياً أو منتهٍ"
    selected_id = (request.GET.get("decision_id") or request.GET.get("correct_id") or "").strip()
    selected = next((row for row in response.get("items", []) if str(row.get("id")) == selected_id), None)
    if selected_id and selected is None:
        try:
            selected = client.get(f"/hr/employment-records/{selected_id}")
            if isinstance(selected, dict) and selected.get("employee_id"):
                selected["employee"] = client.get(f"/hr/employees/{selected['employee_id']}")
        except (ForbiddenException, ApiException):
            selected = None
    employees = []
    if request.GET.get("open_create") == "1":
        try:
            employee_response = client.get("/hr/employees", params={"page": 1, "page_size": 100})
            employees = employee_response.get("items", []) if isinstance(employee_response, dict) else []
        except (ForbiddenException, ApiException):
            employees = []
    return {
        "available": True,
        "items": response.get("items", []),
        "total": response.get("total", 0), "page": response.get("page", 1),
        "pages": response.get("pages", 1), "page_size": response.get("page_size", 10),
        "summary": response.get("summary"), "units": response.get("units", []),
        "selected": selected,
        "employees": employees,
        "filters": params,
    }


def _post_data(request, action):
    form = request.POST
    fields = {
        "employee_create": (
            "/hr/employees",
            ("employee_no", "full_name", "phone", "home_unit_id", "position_title", "hire_date"),
        ),
        "task_create": (
            "/hr/field-tasks",
            ("task_no", "title", "description", "owner_unit_id", "business_date",
             "planned_start_at", "planned_end_at", "location_text"),
        ),
        "request_create": (
            "/hr/workforce-requests",
            ("request_no", "requesting_unit_id", "task_id", "requested_position",
             "headcount", "start_at", "end_at", "priority", "purpose"),
        ),
        "assignment_create": (
            "/hr/assignments",
            ("employee_id", "task_id", "request_id", "beneficiary_unit_id",
             "assignment_kind", "exclusivity", "business_date", "start_at", "end_at", "notes"),
        ),
        "template_create": (
            "/hr/shift-templates",
            ("code", "name_ar", "start_local_time", "end_local_time", "end_day_offset",
             "break_minutes", "timezone_name"),
        ),
        "roster_create": (
            "/hr/shift-roster",
            ("employee_id", "shift_template_id", "owner_unit_id", "work_unit_id",
             "business_date", "start_at", "end_at", "planned_break_minutes",
             "timezone_name", "shift_name_snapshot", "location_text", "notes"),
        ),
        "attendance_create": (
            "/hr/attendance",
            ("employee_id", "attendance_kind", "shift_roster_id", "assignment_id",
             "task_id", "business_date", "status", "check_in_at", "check_out_at", "notes"),
        ),
        "issue_create": (
            "/hr/issues",
            ("employee_id", "attendance_id", "task_id", "issue_type", "business_date",
             "priority", "excuse_decision", "reason", "proposed_solution",
             "responsible_unit_id", "responsible_employee_id"),
        ),
    }
    if action in fields:
        endpoint, names = fields[action]
        data = {name: form.get(name, "").strip() for name in names if form.get(name, "").strip()}
        if action == "request_create":
            data["headcount"] = int(data["headcount"])
        if action == "template_create":
            data["end_day_offset"] = int(data.get("end_day_offset", 0))
            data["break_minutes"] = int(data.get("break_minutes", 0))
        if action == "roster_create":
            data["planned_break_minutes"] = int(data.get("planned_break_minutes", 0))
        if action == "attendance_create":
            for name in ("check_in_at", "check_out_at"):
                if "T" in data.get(name, "") and "+" not in data[name][10:] and "Z" not in data[name]:
                    data[name] = f"{data[name]}+03:00"
        return endpoint, data
    if action == "decision_create":
        employee_id = form.get("employee_id", "").strip()
        endpoint = f"/hr/employees/{employee_id}/employment-records"
        names = ("change_type", "effective_date", "to_unit_id", "to_position_title",
                 "reference_no", "supersedes_record_id", "supersedes_row_version", "reason", "notes")
        data = {name: form.get(name, "").strip() for name in names if form.get(name, "").strip()}
        if "supersedes_row_version" in data:
            data["supersedes_row_version"] = int(data["supersedes_row_version"])
        return endpoint, data
    if action in ("task_transition", "request_transition", "request_approve", "assignment_approve"):
        entity_id = form.get("entity_id", "").strip()
        row_version = int(form.get("row_version", "0"))
        transition = form.get("transition", "").strip()
        reason = form.get("reason", "").strip()
        if action == "task_transition":
            return f"/hr/field-tasks/{entity_id}/transition", {
                "row_version": row_version, "action": transition, "reason": reason,
            }
        if action in ("request_transition", "request_approve"):
            return f"/hr/workforce-requests/{entity_id}/transition", {
                "row_version": row_version,
                "action": "approve" if action == "request_approve" else transition,
                "reason": reason,
            }
        return f"/hr/assignments/{entity_id}/transition", {
            "row_version": row_version, "action": "approve",
        }
    if action in ("attendance_approve", "attendance_correct"):
        attendance_id = form.get("attendance_id", "").strip()
        version = int(form.get("row_version", "0"))
        if action == "attendance_approve":
            return f"/hr/attendance/{attendance_id}/approve", {"row_version": version}
        return f"/hr/attendance/{attendance_id}/correct", {
            "row_version": version,
            "status": form.get("status", "").strip(),
            "reason": form.get("reason", "").strip(),
        }
    if action in ("attendance_submit", "attendance_reject"):
        attendance_id = form.get("attendance_id", "").strip()
        payload = {"row_version": int(form.get("row_version", "0"))}
        if action == "attendance_submit":
            return f"/hr/attendance/{attendance_id}/submit", payload
        payload["reason"] = form.get("reason", "").strip()
        return f"/hr/attendance/{attendance_id}/reject", payload
    if action == "issue_transition":
        issue_id = form.get("issue_id", "").strip()
        return f"/hr/issues/{issue_id}/transition", {
            "row_version": int(form.get("row_version", "0")),
            "action": form.get("transition", "").strip(),
            "resolution_notes": form.get("resolution_notes", "").strip(),
        }
    if action == "report_export":
        code = form.get("report_code", "").strip()
        if code not in ("attendance", "issues", "employees"):
            raise ValueError("نوع التقرير غير صالح")
        start_date = form.get("start_date", "").strip()
        end_date = form.get("end_date", "").strip()
        query = f"?start_date={start_date}&end_date={end_date}" if start_date and end_date else ""
        return f"/hr/reports/{code}/export{query}", {"_download": True}
    raise ValueError("الإجراء غير معروف")


def _datasets(client, section):
    endpoints = {
        "dashboard": (
            ("الموظفون", "/hr/employees", ("employee_no", "full_name", "employment_status", "position_title")),
            ("ورديات اليوم", "/hr/shift-roster", ("business_date", "shift_name_snapshot", "employee_id", "status")),
            ("طلبات القوى العاملة والتغطية", "/hr/workforce-requests", ("request_no", "headcount", "coverage_status", "uncovered")),
            ("الحضور", "/hr/attendance", ("business_date", "attendance_kind", "status", "approval_status", "is_current")),
            ("المشكلات", "/hr/issues", ("issue_type", "business_date", "priority", "solution_status", "excuse_decision", "reason")),
        ),
        "employees": (
            ("قائمة الموظفين", "/hr/employees", ("employee_no", "full_name", "phone", "home_unit_id", "position_title", "employment_status", "row_version")),
        ),
        "workforce": (
            ("المهام الميدانية", "/hr/field-tasks", ("task_no", "title", "business_date", "owner_unit_id", "status")),
            ("طلبات القوى العاملة والتغطية الزمنية", "/hr/workforce-requests", ("request_no", "requested_position", "headcount", "start_at", "end_at", "coverage_status", "uncovered", "status")),
            ("التكليفات", "/hr/assignments", ("employee_id", "task_id", "beneficiary_unit_id", "assignment_kind", "business_date", "status")),
        ),
        "shifts": (
            ("قوالب الورديات", "/hr/shift-templates", ("code", "name_ar", "start_local_time", "end_local_time", "timezone_name")),
            ("جدول الورديات", "/hr/shift-roster", ("business_date", "shift_name_snapshot", "employee_id", "start_at", "end_at", "status")),
            ("سجل الحضور", "/hr/attendance", ("business_date", "employee_id", "attendance_kind", "status", "approval_status", "row_version")),
        ),
        "issues": (
            ("المشكلات", "/hr/issues", ("issue_type", "business_date", "priority", "solution_status", "excuse_decision", "reason", "row_version")),
            ("تقرير الحضور", "/hr/reports/attendance", ("business_date", "attendance_kind", "status", "total")),
            ("تقرير المشكلات", "/hr/reports/issues", ("solution_status", "issue_type", "total")),
        ),
    }
    result = []
    for title, endpoint, columns in endpoints[section]:
        try:
            response = client.get(endpoint)
        except (ForbiddenException, ApiException):
            continue
        items = response if isinstance(response, list) else response.get("items", [])
        if endpoint == "/hr/workforce-requests":
            try:
                coverage_rows = client.get("/hr/workforce-requests/coverage").get("items", [])
            except ForbiddenException:
                coverage_rows = []
            coverage_by_request = {row["request_id"]: row["coverage"] for row in coverage_rows}
            enriched = []
            for item in items:
                coverage = coverage_by_request.get(item["id"], {})
                slices = coverage.get("slices", [])
                item = {
                    **item,
                    "coverage_status": coverage.get("status", "غير متاح"),
                    "uncovered": max((part["uncovered"] for part in slices), default=item.get("headcount", 0)),
                }
                enriched.append(item)
            items = enriched
        result.append({
            "title": title,
            "columns": columns,
            "rows": [{column: row.get(column, "") for column in columns} for row in items],
        })
    return result


TASK_STATUS_LABELS = {
    "draft": "مسودة", "ready": "جاهزة", "in_progress": "جارية",
    "completed": "مكتملة", "cancelled": "ملغاة", "archived": "مؤرشفة",
}


def _workforce_snapshot(client, request):
    """Build the field-task screen from the scoped task endpoint only."""
    params = {key: request.GET.get(key, "").strip() for key in (
        "q", "status", "business_date_from", "business_date_to", "unit_id"
    ) if request.GET.get(key, "").strip()}
    params["page"] = request.GET.get("page", "1")
    params["page_size"] = request.GET.get("page_size", "10")
    try:
        response = client.get("/hr/field-tasks", params=params)
    except (ForbiddenException, ApiException):
        return {"available": False, "items": [], "filters": params, "summary": {}}
    payload = response if isinstance(response, dict) else {"items": response or []}
    rows = payload.get("items", [])
    now = timezone.now()
    counts = {status: 0 for status in TASK_STATUS_LABELS}
    for row in rows:
        status = row.get("status")
        counts[status] = counts.get(status, 0) + 1
        row["status_label"] = TASK_STATUS_LABELS.get(status, "غير متاح")
        row["is_late"] = bool(
            row.get("planned_end_at") and status not in {"completed", "cancelled", "archived"}
            and str(row.get("planned_end_at")) < now.isoformat()
        )
    total = payload.get("total", len(rows))
    page = int(payload.get("page", params["page"]))
    page_size = int(payload.get("page_size", params["page_size"]))
    pages = max((int(total) + page_size - 1) // page_size, 1)
    units = payload.get("units", [])
    if request.GET.get("open_create") == "1" and not units:
        try:
            employees = client.get("/hr/employees", params={"page": 1, "page_size": 100})
            employee_rows = employees.get("items", []) if isinstance(employees, dict) else []
            units = sorted({(row.get("home_unit_id"), row.get("home_unit_name", "غير متاح"))
                            for row in employee_rows if row.get("home_unit_id")})
        except (ForbiddenException, ApiException):
            units = []
    return {
        "available": True, "items": rows, "total": total, "page": page,
        "page_size": page_size, "pages": pages, "counts": counts,
        "summary": payload.get("summary", {}), "filters": params,
        "units": units,
        "late": sum(1 for row in rows if row.get("is_late")),
    }


REQUEST_STATUS_LABELS = {
    "draft": "مسودة", "submitted": "قيد المراجعة", "approved": "معتمد",
    "rejected": "مرفوض", "partially_filled": "تغطية جزئية", "filled": "مغطى بالكامل",
    "closed": "مغلق", "cancelled": "ملغى",
}
REQUEST_COVERAGE_LABELS = {"approved": "غير مغطى", "partially_filled": "تغطية جزئية", "filled": "مغطى بالكامل"}


def _workforce_requests_snapshot(client, request):
    params = {key: request.GET.get(key, "").strip() for key in (
        "q", "status", "business_date_from", "business_date_to", "unit_id"
    ) if request.GET.get(key, "").strip()}
    try:
        payload = client.get("/hr/workforce-requests", params=params)
        rows = payload if isinstance(payload, list) else (payload.get("items", []) if isinstance(payload, dict) else [])
        coverage_payload = client.get("/hr/workforce-requests/coverage")
        coverage_rows = coverage_payload.get("items", []) if isinstance(coverage_payload, dict) else []
    except (ForbiddenException, ApiException):
        return {"available": False, "items": [], "filters": params}
    coverage_by_id = {row.get("request_id"): row.get("coverage", {}) for row in coverage_rows}
    enriched = []
    for row in rows:
        coverage = coverage_by_id.get(row.get("id"), {})
        slices = coverage.get("slices", [])
        covered = max((part.get("covered_count", 0) for part in slices), default=0)
        coverage_status = coverage.get("status") or "approved"
        item = {**row, "status_label": REQUEST_STATUS_LABELS.get(row.get("status"), "غير متاح"),
                "coverage_status": coverage_status, "coverage_label": REQUEST_COVERAGE_LABELS.get(coverage_status, "غير متاح"),
                "covered_count": covered, "coverage": coverage,
                "coverage_percent": min(round(covered * 100 / row.get("headcount", 1)), 100) if row.get("headcount") else 0}
        if request.GET.get("coverage_status") and coverage_status != request.GET.get("coverage_status"):
            continue
        enriched.append(item)
    try:
        page_size = min(max(int(request.GET.get("page_size", "10")), 1), 100)
    except ValueError:
        page_size = 10
    try:
        page = max(int(request.GET.get("page", "1")), 1)
    except ValueError:
        page = 1
    total = len(enriched)
    pages = max((total + page_size - 1) // page_size, 1)
    selected_id = request.GET.get("request_id", "").strip()
    selected = next((item for item in enriched if str(item.get("id")) == selected_id), None)
    if selected and not selected.get("coverage"):
        try:
            selected["coverage"] = client.get(f"/hr/workforce-requests/{selected_id}/coverage").get("coverage", {})
        except (ForbiddenException, ApiException):
            pass
    tasks = []
    units = []
    if request.GET.get("open_create") == "1":
        try:
            task_payload = client.get("/hr/field-tasks", params={"page": 1, "page_size": 100})
            tasks = task_payload.get("items", []) if isinstance(task_payload, dict) else []
            employee_payload = client.get("/hr/employees", params={"page": 1, "page_size": 100})
            employees = employee_payload.get("items", []) if isinstance(employee_payload, dict) else []
            units = sorted({(row.get("home_unit_id"), row.get("home_unit_name", "غير متاح")) for row in employees if row.get("home_unit_id")})
        except (ForbiddenException, ApiException):
            pass
    return {"available": True, "items": enriched[(page - 1) * page_size:page * page_size], "all_items": enriched,
            "total": total, "page": page, "pages": pages, "page_size": page_size,
            "selected": selected, "tasks": tasks, "units": units, "filters": params, "summary": {
                "total": total, "review": sum(1 for item in enriched if item.get("status") == "submitted"),
                "filled": sum(1 for item in enriched if item.get("coverage_status") == "filled"),
                "partial": sum(1 for item in enriched if item.get("coverage_status") == "partially_filled"),
            }}


ASSIGNMENT_STATUS_LABELS = {"draft": "مسودة", "pending": "بانتظار الاعتماد", "approved": "معتمد", "active": "نشط", "cancelled": "ملغى"}
ASSIGNMENT_KIND_LABELS = {"direct_task": "مهمة مباشرة", "supervision": "إشراف", "unit_allocation": "توزيع وحدة", "historical_import": "سجل تاريخي"}


def _assignments_snapshot(client, request):
    params = {key: request.GET.get(key, "").strip() for key in ("employee_id", "status", "assignment_kind") if request.GET.get(key, "").strip()}
    try:
        payload = client.get("/hr/assignments", params=params)
        rows = payload if isinstance(payload, list) else (payload.get("items", []) if isinstance(payload, dict) else [])
    except (ForbiddenException, ApiException):
        return {"available": False, "items": [], "filters": params}
    employees = tasks = requests = []
    units = []
    if request.GET.get("open_create") == "1":
        try:
            employee_payload = client.get("/hr/employees", params={"page": 1, "page_size": 100})
            employees = employee_payload.get("items", []) if isinstance(employee_payload, dict) else []
            units = sorted({(row.get("home_unit_id"), row.get("home_unit_name", "غير متاح")) for row in employees if row.get("home_unit_id")})
            task_payload = client.get("/hr/field-tasks", params={"page": 1, "page_size": 100})
            tasks = task_payload.get("items", []) if isinstance(task_payload, dict) else []
            request_payload = client.get("/hr/workforce-requests")
            requests = request_payload.get("items", []) if isinstance(request_payload, dict) else []
        except (ForbiddenException, ApiException):
            pass
    employee_map = {str(row.get("id")): row for row in employees}
    task_map = {str(row.get("id")): row for row in tasks}
    request_map = {str(row.get("id")): row for row in requests}
    for row in rows:
        employee = employee_map.get(str(row.get("employee_id")), {})
        task = task_map.get(str(row.get("task_id")), {})
        req = request_map.get(str(row.get("request_id")), {})
        row.update({"employee_name": employee.get("full_name", "غير متاح"), "employee_no": employee.get("employee_no", ""),
                    "task_title": task.get("title", "طلب مستقل"), "task_no": task.get("task_no", ""),
                    "request_no": req.get("request_no", ""), "status_label": ASSIGNMENT_STATUS_LABELS.get(row.get("status"), "غير متاح"),
                    "kind_label": ASSIGNMENT_KIND_LABELS.get(row.get("assignment_kind"), "غير متاح")})
    if request.GET.get("q"):
        needle = request.GET["q"].strip().lower()
        rows = [row for row in rows if needle in " ".join(str(row.get(key, "")) for key in ("employee_name", "employee_no", "task_title", "task_no", "request_no")).lower()]
    if request.GET.get("assignment_kind"):
        rows = [row for row in rows if row.get("assignment_kind") == request.GET["assignment_kind"]]
    if request.GET.get("status"):
        rows = [row for row in rows if row.get("status") == request.GET["status"]]
    try:
        page_size = min(max(int(request.GET.get("page_size", "10")), 1), 100)
    except ValueError:
        page_size = 10
    try:
        page = max(int(request.GET.get("page", "1")), 1)
    except ValueError:
        page = 1
    total = len(rows)
    try:
        week_start = date.fromisoformat(request.GET.get("week", "")) if request.GET.get("week") else date.today() - timedelta(days=date.today().weekday())
    except ValueError:
        week_start = date.today() - timedelta(days=date.today().weekday())
    week_days = [(week_start + timedelta(days=index)).isoformat() for index in range(7)]
    return {"available": True, "items": rows[(page - 1) * page_size:page * page_size], "all_items": rows,
            "total": total, "page": page, "page_size": page_size, "pages": max((total + page_size - 1) // page_size, 1),
            "employees": employees, "tasks": tasks, "requests": requests, "units": units, "filters": params,
            "week_days": week_days,
            "summary": {"active": sum(1 for row in rows if row.get("status") in ("approved", "active")),
                        "pending": sum(1 for row in rows if row.get("status") == "pending"),
                        "conflicts": None, "available": None}}


EMPLOYEE_STATUS_LABELS = {
    "active": "نشط",
    "suspended": "موقوف",
    "terminated": "منتهية الخدمة",
}


def _employee_snapshot(client, request):
    params = {
        key: request.GET.get(key, "").strip()
        for key in ("q", "unit_id", "position_title", "employment_status")
        if request.GET.get(key, "").strip()
    }
    try:
        page = max(int(request.GET.get("page", "1")), 1)
    except ValueError:
        page = 1
    try:
        page_size = min(max(int(request.GET.get("page_size", "20")), 1), 100)
    except ValueError:
        page_size = 20
    params.update({"page": page, "page_size": page_size})
    response = client.get("/hr/employees", params=params)
    payload = response if isinstance(response, dict) else {"items": response or []}
    rows = payload.get("items", [])
    for row in rows:
        row["status_label"] = EMPLOYEE_STATUS_LABELS.get(row.get("employment_status"), "غير متاح")
        row["profile_available"] = False
        # The API may serialize UUIDs as compact hex; Django's uuid URL
        # converter requires the canonical hyphenated representation.
        try:
            row["id"] = str(UUID(str(row.get("id"))))
            row["url_id"] = row["id"]
        except (ValueError, TypeError, AttributeError):
            row["url_id"] = row.get("id")
    summary = payload.get("summary", {})
    return {
        "rows": rows,
        "total": payload.get("total", len(rows)),
        "page": payload.get("page", page),
        "page_size": payload.get("page_size", page_size),
        "pages": max((int(payload.get("total", len(rows))) + page_size - 1) // page_size, 1),
        "summary": summary,
        "filters": {
            "q": request.GET.get("q", ""),
            "unit_id": request.GET.get("unit_id", ""),
            "position_title": request.GET.get("position_title", ""),
            "employment_status": request.GET.get("employment_status", ""),
            "page_size": page_size,
        },
        "positions": sorted({row.get("position_title") for row in rows if row.get("position_title")}),
        "units": sorted({(row.get("home_unit_id"), row.get("home_unit_name", "غير متاح")) for row in rows if row.get("home_unit_id")}),
    }


ISSUE_TYPE_LABELS = {"absence": "غياب", "late": "تأخر", "early_exit": "انصراف مبكر", "missing_coverage": "نقص تغطية", "field_problem": "مشكلة ميدانية", "other": "أخرى"}
ISSUE_STATUS_LABELS = {"not_started": "لم تبدأ المعالجة", "in_progress": "قيد المعالجة", "resolved": "تم الحل", "closed": "مغلقة", "cancelled": "ملغاة"}
ISSUE_PRIORITY_LABELS = {"low": "منخفضة", "normal": "عادية", "high": "عالية", "urgent": "عاجلة"}
EXCUSE_LABELS = {"not_applicable": "غير منطبق", "pending": "بانتظار القرار", "accepted": "مقبول", "rejected": "مرفوض"}


def _issue_snapshot(client, request):
    try:
        payload = client.get("/hr/issues")
    except (ForbiddenException, ApiException):
        return {"available": False, "items": [], "all_items": [], "selected": None, "total": 0, "page": 1, "pages": 1, "page_size": 10, "filters": {}, "summary": {"open": None, "in_progress": None, "overdue": None, "closed": None}}
    rows = list(payload.get("items", []) if isinstance(payload, dict) else payload or [])
    for row in rows:
        row["issue_type_label"] = ISSUE_TYPE_LABELS.get(row.get("issue_type"), "أخرى")
        row["status_label"] = ISSUE_STATUS_LABELS.get(row.get("solution_status"), "غير متاح")
        row["priority_label"] = ISSUE_PRIORITY_LABELS.get(row.get("priority"), row.get("priority") or "غير متاح")
        row["excuse_label"] = EXCUSE_LABELS.get(row.get("excuse_decision"), "غير متاح")
        row["employee_name"] = row.get("employee_name") or "مشكلة تشغيلية عامة"
        row["employee_no"] = row.get("employee_no") or "—"
        row["responsible_name"] = row.get("responsible_employee_name") or "غير مسند"
        row["unit_name"] = row.get("responsible_unit_name") or "غير محددة"
    filters = {key: request.GET.get(key, "").strip() for key in ("q", "issue_type", "solution_status", "priority", "excuse_decision", "business_date_from", "business_date_to")}
    q = filters["q"].lower()
    filtered = [row for row in rows if ((not q or q in str(row.get("employee_name", "")).lower() or q in str(row.get("employee_no", "")).lower() or q in str(row.get("id", "")).lower() or q in str(row.get("reason", "")).lower()) and (not filters["issue_type"] or row.get("issue_type") == filters["issue_type"]) and (not filters["solution_status"] or row.get("solution_status") == filters["solution_status"]) and (not filters["priority"] or row.get("priority") == filters["priority"]) and (not filters["excuse_decision"] or row.get("excuse_decision") == filters["excuse_decision"]) and (not filters["business_date_from"] or str(row.get("business_date", "")) >= filters["business_date_from"]) and (not filters["business_date_to"] or str(row.get("business_date", "")) <= filters["business_date_to"]))]
    filtered.sort(key=lambda row: (str(row.get("business_date", "")), str(row.get("created_at", ""))), reverse=True)
    selected = next((row for row in filtered if str(row.get("id")) == request.GET.get("issue_id", "")), None)
    try:
        page_size = min(max(int(request.GET.get("page_size", "10")), 1), 50); page = max(int(request.GET.get("page", "1")), 1)
    except ValueError:
        page_size, page = 10, 1
    total = len(filtered); pages = max((total + page_size - 1) // page_size, 1); page = min(page, pages)
    open_rows = [row for row in rows if row.get("solution_status") in ("not_started", "in_progress")]
    return {"available": True, "items": filtered[(page - 1) * page_size:page * page_size], "all_items": filtered, "selected": selected, "total": total, "page": page, "pages": pages, "page_size": page_size, "filters": filters, "summary": {"open": len(open_rows), "in_progress": sum(row.get("solution_status") == "in_progress" for row in rows), "overdue": None, "closed": sum(row.get("solution_status") == "closed" for row in rows)}}


SHIFT_STATUS_LABELS = {
    "draft": "مسودة",
    "confirmed": "معتمدة",
    "completed": "مكتملة",
    "cancelled": "ملغاة",
}


def _shifts_snapshot(client, request):
    """Build the scheduling screen from the scoped HR shift services."""
    today = timezone.localdate()
    try:
        week_start = date.fromisoformat(request.GET.get("week", ""))
    except ValueError:
        week_start = today - timedelta(days=today.weekday())
    if week_start.weekday() != 0:
        week_start -= timedelta(days=week_start.weekday())
    week_days = [week_start + timedelta(days=index) for index in range(7)]
    filters = {key: request.GET.get(key, "").strip() for key in (
        "q", "status", "business_date", "page_size"
    )}
    try:
        page_size = min(max(int(filters["page_size"] or "10"), 1), 50)
    except ValueError:
        page_size = 10

    try:
        template_payload = client.get("/hr/shift-templates")
        roster_payload = client.get("/hr/shift-roster")
        employee_payload = client.get("/hr/employees", params={"page": 1, "page_size": 100})
    except (ForbiddenException, ApiException):
        return {"available": False, "items": [], "templates": [], "employees": [],
                "week_days": week_days, "filters": filters, "conflicts": "غير متاح"}

    templates = template_payload.get("items", []) if isinstance(template_payload, dict) else []
    rows = roster_payload.get("items", []) if isinstance(roster_payload, dict) else []
    employees = employee_payload.get("items", []) if isinstance(employee_payload, dict) else []
    employee_map = {str(row.get("id")): row for row in employees}
    template_map = {str(row.get("id")): row for row in templates}
    units = sorted({(row.get("home_unit_id"), row.get("home_unit_name") or "الإدارة الأساسية")
                    for row in employees if row.get("home_unit_id")}, key=lambda item: item[1])
    for row in rows:
        employee = employee_map.get(str(row.get("employee_id")), {})
        template = template_map.get(str(row.get("shift_template_id")), {})
        row["employee_name"] = employee.get("full_name") or "موظف غير متاح"
        row["employee_no"] = employee.get("employee_no", "")
        row["shift_label"] = row.get("shift_name_snapshot") or template.get("name_ar") or "وردية"
        row["status_label"] = SHIFT_STATUS_LABELS.get(row.get("status"), "غير متاح")
        row["status_class"] = row.get("status", "unavailable")
        row["start_label"] = str(row.get("start_at", ""))[:16].replace("T", " ")
        row["end_label"] = str(row.get("end_at", ""))[:16].replace("T", " ")

    q = filters["q"].lower()
    filtered = [row for row in rows if (
        (not q or q in str(row.get("employee_name", "")).lower() or
         q in str(row.get("employee_no", "")).lower() or
         q in str(row.get("shift_label", "")).lower()) and
        (not filters["status"] or row.get("status") == filters["status"]) and
        (not filters["business_date"] or row.get("business_date") == filters["business_date"])
    )]
    filtered.sort(key=lambda row: (str(row.get("business_date", "")), row.get("employee_name", "")))
    total = len(filtered)
    page = max(int(request.GET.get("page", "1") or 1), 1)
    pages = max((total + page_size - 1) // page_size, 1)
    page = min(page, pages)
    page_rows = filtered[(page - 1) * page_size:page * page_size]

    employees_in_week = {}
    for row in filtered:
        day = str(row.get("business_date", ""))
        if day in {item.isoformat() for item in week_days}:
            employees_in_week.setdefault(str(row.get("employee_id")), {
                "id": row.get("employee_id"), "name": row.get("employee_name"),
                "employee_no": row.get("employee_no"), "days": {},
            })["days"][day] = row
    weekly_rows = list(employees_in_week.values())
    for person in weekly_rows:
        person["cells"] = [person["days"].get(day.isoformat()) for day in week_days]
    today_count = sum(1 for row in rows if row.get("business_date") == today.isoformat())
    active_templates = sum(1 for row in templates if row.get("is_active", True))
    pending_count = sum(1 for row in rows if row.get("status") == "draft")
    return {
        "available": True, "items": page_rows, "total": total, "page": page,
        "pages": pages, "page_size": page_size, "all_rows": rows,
        "templates": templates, "employees": employees, "employee_map": employee_map,
        "units": units,
        "weekly_rows": weekly_rows, "week_days": week_days, "week_start": week_start,
        "today_count": today_count, "active_templates": active_templates,
        "pending_count": pending_count, "conflicts": "غير متاح", "filters": filters,
    }


ATTENDANCE_STATUS_LABELS = {
    "present": "حاضر",
    "absent": "غائب",
    "partial": "حضور جزئي",
    "pending": "بانتظار الحسم",
    "late": "متأخر",
    "excused": "بعذر",
    "unknown": "غير محسوم",
}
ATTENDANCE_APPROVAL_LABELS = {
    "draft": "مسودة",
    "submitted": "قيد المراجعة",
    "approved": "معتمد",
    "rejected": "مرفوض",
}


def _attendance_snapshot(client, request):
    """Build the daily attendance view from scoped shift and attendance records only."""
    try:
        business_day = date.fromisoformat(request.GET.get("business_date", ""))
    except ValueError:
        business_day = timezone.localdate()
    day_value = business_day.isoformat()
    filters = {
        key: request.GET.get(key, "").strip()
        for key in ("q", "attendance_status", "shift_id", "unit_id", "location", "page_size")
    }
    filters["business_date"] = day_value
    try:
        page_size = min(max(int(filters["page_size"] or "10"), 1), 50)
    except ValueError:
        page_size = 10

    try:
        roster_response = client.get("/hr/shift-roster")
        attendance_response = client.get("/hr/attendance", params={"business_date": day_value})
        employee_response = client.get("/hr/employees", params={"page": 1, "page_size": 100})
    except (ForbiddenException, ApiException):
        return {
            "available": False, "items": [], "filters": filters, "summary": {},
            "shifts": [], "units": [], "locations": [], "tasks_available": False,
            "issues_available": False, "pages": 1, "page": 1, "total": 0,
        }

    roster_rows = roster_response.get("items", []) if isinstance(roster_response, dict) else []
    attendance_rows = attendance_response.get("items", []) if isinstance(attendance_response, dict) else []
    employees = employee_response.get("items", []) if isinstance(employee_response, dict) else []
    employee_map = {str(employee.get("id")): employee for employee in employees}
    confirmed_rosters = [
        row for row in roster_rows
        if row.get("business_date") == day_value and row.get("status") in ("confirmed", "completed")
    ]
    base_by_roster = {
        str(row.get("shift_roster_id")): row for row in attendance_rows
        if row.get("attendance_kind") == "base_shift" and row.get("is_current") in (True, 1)
        and row.get("shift_roster_id")
    }
    task_rows = [
        row for row in attendance_rows
        if row.get("attendance_kind") == "task_participation" and row.get("is_current") in (True, 1)
    ]
    task_counts = {}
    for row in task_rows:
        task_counts[str(row.get("employee_id"))] = task_counts.get(str(row.get("employee_id")), 0) + 1

    tasks = None
    issues = None
    try:
        task_response = client.get("/hr/field-tasks")
        tasks = task_response.get("items", []) if isinstance(task_response, dict) else []
    except (ForbiddenException, ApiException):
        pass
    try:
        issue_response = client.get("/hr/issues")
        issues = issue_response.get("items", []) if isinstance(issue_response, dict) else []
    except (ForbiddenException, ApiException):
        pass

    rows = []
    for roster in confirmed_rosters:
        employee = employee_map.get(str(roster.get("employee_id")), {})
        attendance = base_by_roster.get(str(roster.get("id")))
        employee_id = str(roster.get("employee_id"))
        unit_id = str(employee.get("home_unit_id") or "")
        unit_name = employee.get("home_unit_name") or "الإدارة الأساسية"
        shift_label = roster.get("shift_name_snapshot") or "وردية مؤكدة"
        raw_status = attendance.get("status") if attendance else "unrecorded"
        row = {
            "id": str(roster.get("id")),
            "employee_id": employee_id,
            "employee_name": employee.get("full_name") or "موظف ضمن النطاق",
            "employee_no": employee.get("employee_no") or "—",
            "unit_id": unit_id,
            "unit_name": unit_name,
            "shift_label": shift_label,
            "location": roster.get("location_text") or "—",
            "start_label": str(roster.get("start_at") or "")[:16].replace("T", " ") or "—",
            "end_label": str(roster.get("end_at") or "")[:16].replace("T", " ") or "—",
            "attendance": attendance,
            "attendance_status": raw_status,
            "attendance_label": ATTENDANCE_STATUS_LABELS.get(raw_status, "لم يسجل بعد") if attendance else "لم يسجل بعد",
            "attendance_class": raw_status if attendance else "unrecorded",
            "approval_label": ATTENDANCE_APPROVAL_LABELS.get(attendance.get("approval_status"), "غير متاح") if attendance else "",
            "check_in": str(attendance.get("check_in_at") or "")[:16].replace("T", " ") if attendance else "—",
            "check_out": str(attendance.get("check_out_at") or "")[:16].replace("T", " ") if attendance else "—",
            "task_count": task_counts.get(employee_id, 0),
        }
        rows.append(row)

    q = filters["q"].lower()
    filtered = [
        row for row in rows if (
            (not q or q in row["employee_name"].lower() or q in row["employee_no"].lower())
            and (not filters["attendance_status"] or row["attendance_status"] == filters["attendance_status"])
            and (not filters["shift_id"] or row["id"] == filters["shift_id"])
            and (not filters["unit_id"] or row["unit_id"] == filters["unit_id"])
            and (not filters["location"] or row["location"] == filters["location"])
        )
    ]
    filtered.sort(key=lambda row: (row["unit_name"], row["employee_name"]))
    total = len(filtered)
    try:
        page = max(int(request.GET.get("page", "1") or 1), 1)
    except ValueError:
        page = 1
    pages = max((total + page_size - 1) // page_size, 1)
    page = min(page, pages)
    page_rows = filtered[(page - 1) * page_size:page * page_size]
    recorded = [row for row in rows if row["attendance"]]
    confirmed_absent = sum(
        row["attendance_status"] == "absent" and row["attendance"].get("approval_status") == "approved"
        for row in rows if row["attendance"]
    )
    unresolved = sum(
        row["attendance_status"] == "pending"
        or row["attendance"].get("approval_status") in ("draft", "submitted")
        for row in rows if row["attendance"]
    )
    units = sorted({(row["unit_id"], row["unit_name"]) for row in rows if row["unit_id"]}, key=lambda item: item[1])
    shifts = sorted({(row["id"], row["shift_label"]) for row in rows}, key=lambda item: item[1])
    locations = sorted({row["location"] for row in rows if row["location"] != "—"})
    open_issues = [
        item for item in (issues or [])
        if item.get("business_date") == day_value and item.get("solution_status") not in ("closed", "cancelled")
    ] if issues is not None else []
    day_tasks = [item for item in (tasks or []) if item.get("business_date") == day_value] if tasks is not None else []
    return {
        "available": True, "items": page_rows, "all_rows": rows, "filters": filters,
        "total": total, "page": page, "pages": pages, "page_size": page_size,
        "shifts": shifts, "units": units, "locations": locations,
        "tasks_available": tasks is not None, "issues_available": issues is not None,
        "summary": {
            "scheduled": len(rows), "recorded": len(recorded), "absent": confirmed_absent,
            "unresolved": unresolved, "missing": max(len(rows) - len(recorded), 0),
            "tasks": len(day_tasks), "open_issues": len(open_issues),
            "participations": len(task_rows),
        },
    }


def _reports_snapshot(client, identity, request):
    """Compose the reports workspace from scoped HR records; unavailable means unavailable."""
    def load(permission, endpoint, params=None):
        if not _allowed(identity, permission):
            return None
        try:
            response = client.get(endpoint, params=params)
        except (ForbiddenException, ApiException):
            return None
        return response.get("items", []) if isinstance(response, dict) else (response if isinstance(response, list) else [])

    today = timezone.localdate()
    # The HR API caps a page at 100 rows; requesting 1000 turns a valid
    # report into an unavailable report response.
    employees = load("hr.employees.view", "/hr/employees", {"page": 1, "page_size": 100})
    roster = load("hr.shift.view", "/hr/shift-roster")
    attendance = load("hr.attendance.view", "/hr/attendance", {"business_date": today.isoformat()})
    issues = load("hr.issue.view", "/hr/issues")
    tasks = load("hr.task.view", "/hr/field-tasks")
    period = request.GET.get("period", "month")
    active_employees = [row for row in employees or [] if row.get("employment_status") == "active"]
    scheduled = [row for row in roster or [] if row.get("status") in ("confirmed", "completed")]
    recorded = [row for row in attendance or [] if row.get("attendance_kind") == "base_shift" and row.get("is_current") in (True, 1)]
    open_issues = [row for row in issues or [] if row.get("solution_status") not in ("closed", "cancelled")]
    active_tasks = [row for row in tasks or [] if row.get("status") == "in_progress"]

    units = {}
    for row in employees or []:
        key = row.get("home_unit_id") or "unknown"
        label = row.get("home_unit_name") or "غير متاح"
        units.setdefault(str(key), {"label": label, "value": 0})["value"] += 1
    unit_rows = sorted(units.values(), key=lambda item: item["value"], reverse=True)[:8]
    unit_max = max([item["value"] for item in unit_rows] or [1])
    for item in unit_rows:
        item["width"] = round(item["value"] * 100 / unit_max)

    shifts = {}
    for row in scheduled:
        label = row.get("shift_name_snapshot") or "غير متاح"
        shifts[label] = shifts.get(label, 0) + 1
    shift_rows = sorted(({"label": key, "value": value} for key, value in shifts.items()), key=lambda item: item["value"], reverse=True)[:6]
    shift_total = sum(item["value"] for item in shift_rows) or 1
    for item in shift_rows:
        item["percent"] = round(item["value"] * 100 / shift_total)

    return {
        "available": any(value is not None for value in (employees, roster, attendance, issues, tasks)),
        "period": period,
        "start_date": today.replace(day=1).isoformat(),
        "end_date": today.isoformat(),
        "cards": [
            {"label": "إجمالي الموظفين", "value": len(employees) if employees is not None else "غير متاح", "note": "من السجل المسموح به"},
            {"label": "الحضور المسجل اليوم", "value": len(recorded) if attendance is not None else "غير متاح", "note": "لا يثبت الغياب دون سجل معتمد"},
            {"label": "المهام الجارية", "value": len(active_tasks) if tasks is not None else "غير متاح", "note": "بحالة قيد التنفيذ"},
            {"label": "المشكلات المفتوحة", "value": len(open_issues) if issues is not None else "غير متاح", "note": "تحتاج متابعة أو معالجة"},
        ],
        "unit_rows": unit_rows,
        "unit_available": employees is not None,
        "shift_rows": shift_rows,
        "shift_available": roster is not None,
        "attendance_available": attendance is not None,
        "attendance_value": len(recorded),
        "employee_rows": (employees or [])[:10],
        "latest_available": False,
        "export_allowed": _allowed(identity, "hr.report.export"),
        "detail_rows": (attendance or [])[:20],
    }


def _dashboard_snapshot(client, identity, today):
    errors = []

    def load(permission, endpoint, params=None):
        if not _allowed(identity, permission):
            return None
        try:
            response = client.get(endpoint, params=params)
        except UnauthorizedException:
            raise
        except ForbiddenException:
            return None
        except ApiException:
            errors.append(endpoint)
            return None
        if isinstance(response, list):
            return response
        return response.get("items", []) if isinstance(response, dict) else []

    employees = load("hr.employees.view", "/hr/employees")
    roster_rows = load("hr.shift.view", "/hr/shift-roster")
    shifts = [
        row for row in roster_rows or []
        if row.get("business_date") == today and row.get("status") != "cancelled"
    ]
    attendance_shifts = [
        row for row in shifts if row.get("status") in ("confirmed", "completed")
    ]
    attendance = load(
        "hr.attendance.view", "/hr/attendance", {"business_date": today}
    )
    tasks = load("hr.task.view", "/hr/field-tasks")
    requests = load("hr.workforce.view", "/hr/workforce-requests")
    issues = load("hr.issue.view", "/hr/issues")

    def metric(title, value, detail, section, permission, available=True):
        permitted = _allowed(identity, permission)
        return {
            "title": title,
            "value": value if available and permitted else "—",
            "detail": detail if available and permitted else (
                "تعذر تحميل البيانات" if permitted else "لا تتوفر صلاحية عرض البيانات"
            ),
            "href": f"{reverse('hr:home')}?section={section}" if permitted else "",
        }

    active_employees = sum(row.get("employment_status") == "active" for row in employees or [])
    roster_ids = {row.get("id") for row in attendance_shifts if row.get("id")}
    recorded_roster_ids = {
        row.get("shift_roster_id")
        for row in attendance or []
        if row.get("is_current") in (True, 1)
        and row.get("attendance_kind") == "base_shift"
        and row.get("shift_roster_id") in roster_ids
    }
    attendance_available = roster_rows is not None and attendance is not None
    if attendance_shifts and attendance_available:
        attendance_value = f"{len(recorded_roster_ids) * 100 // len(attendance_shifts)}%"
        attendance_detail = (
            f"{len(recorded_roster_ids)} من {len(attendance_shifts)} وردية لها سجل حضور؛ "
            "عدم وجود سجل لا يثبت الغياب"
        )
    elif not attendance_shifts and roster_rows is not None and attendance is not None:
        attendance_value = "—"
        attendance_detail = (
            "لا توجد ورديات مؤكدة أو مكتملة اليوم"
            if shifts else "لا توجد ورديات مسجلة لهذا اليوم"
        )
    else:
        attendance_value = "—"
        attendance_detail = "تعذر تحميل بيانات الورديات أو الحضور"

    active_tasks = [
        row for row in tasks or [] if row.get("status") == "in_progress"
    ]
    open_issues = [
        row for row in issues or []
        if row.get("solution_status") not in ("closed", "cancelled")
    ]
    pending_requests = [
        row for row in requests or [] if row.get("status") == "submitted"
    ]
    unconfirmed_shifts = [row for row in shifts if row.get("status") == "draft"]
    missing_attendance = max(len(attendance_shifts) - len(recorded_roster_ids), 0)

    metrics = [
        metric(
            "إجمالي الموظفين",
            len(employees or []),
            "ضمن نطاق الصلاحية المتاح",
            "employees",
            "hr.employees.view",
            employees is not None,
        ),
        metric(
            "الموظفون النشطون",
            active_employees,
            "بحسب الحالة الوظيفية المسجلة",
            "employees",
            "hr.employees.view",
            employees is not None,
        ),
        metric(
            "ورديات اليوم",
            len(shifts),
            "ضمن نطاق الصلاحية المتاح",
            "shifts",
            "hr.shift.view",
            roster_rows is not None,
        ),
        metric(
            "اكتمال تسجيل الحضور",
            attendance_value,
            attendance_detail,
            "shifts",
            "hr.attendance.view",
            attendance_available,
        ),
        metric(
            "المهام الجارية",
            len(active_tasks),
            "حالتها «قيد التنفيذ»",
            "workforce",
            "hr.task.view",
            tasks is not None,
        ),
        metric(
            "المشكلات المفتوحة",
            len(open_issues),
            "تحتاج إلى متابعة أو معالجة",
            "issues",
            "hr.issue.view",
            issues is not None,
        ),
    ]

    section_urls = {
        "employees": f"{reverse('hr:home')}?section=employees",
        "workforce": f"{reverse('hr:home')}?section=workforce",
        "shifts": f"{reverse('hr:home')}?section=shifts",
        "issues": f"{reverse('hr:home')}?section=issues",
    }
    alerts = []
    for count, title, description, section in (
        (len(unconfirmed_shifts), "ورديات اليوم غير مؤكدة", "راجع جدول الورديات قبل بدء التشغيل.", "shifts"),
        (len(pending_requests), "طلبات قوى عاملة بانتظار القرار", "راجع الطلبات المقدمة ضمن نطاقك.", "workforce"),
        (len(open_issues), "مشكلات تشغيلية مفتوحة", "تابع المعالجة أو قرار الإغلاق حسب صلاحيتك.", "issues"),
    ):
        if count:
            alerts.append({
                "title": title,
                "description": description,
                "count": count,
                "href": section_urls[section],
            })

    recent_updates = []
    for rows, title, section, date_key in (
        (tasks or [], "تحديث في مهمة ميدانية", "workforce", "updated_at"),
        (requests or [], "تحديث في طلب قوى عاملة", "workforce", "updated_at"),
        (shifts, "تحديث في جدول الورديات", "shifts", "updated_at"),
        (issues or [], "تحديث في مشكلة تشغيلية", "issues", "updated_at"),
    ):
        for row in rows:
            recent_updates.append({
                "title": title,
                "date": row.get(date_key) or row.get("created_at") or row.get("business_date") or "",
                "href": section_urls[section],
            })
    recent_updates.sort(key=lambda item: item["date"], reverse=True)

    if _allowed(identity, "hr.attendance.record") and missing_attendance:
        next_action = {
            "title": "تسجيل حضور اليوم",
            "description": f"لا يظهر سجل حضور لـ {missing_attendance} وردية مجدولة. عدم وجود تسجيل لا يعني إثبات الغياب.",
            "href": section_urls["shifts"],
            "label": "الانتقال إلى الورديات والحضور",
        }
    elif _allowed(identity, "hr.workforce.approve") and pending_requests:
        next_action = {
            "title": "مراجعة طلبات القوى العاملة",
            "description": f"هناك {len(pending_requests)} طلبات مقدمة تنتظر قراراً.",
            "href": section_urls["workforce"],
            "label": "مراجعة الطلبات",
        }
    elif _allowed(identity, "hr.issue.manage") and open_issues:
        next_action = {
            "title": "متابعة مشكلة تشغيلية",
            "description": f"هناك {len(open_issues)} مشكلات مفتوحة ضمن النطاق المتاح.",
            "href": section_urls["issues"],
            "label": "متابعة المشكلات",
        }
    else:
        first_section = next(
            (section for section, permissions in (
                ("employees", ("hr.employees.view",)),
                ("workforce", ("hr.workforce.view", "hr.task.view")),
                ("shifts", ("hr.shift.view", "hr.attendance.view")),
                ("issues", ("hr.issue.view", "hr.report.view")),
            ) if _allowed_any(identity, *permissions)),
            "",
        )
        next_action = {
            "title": "ابدأ من مساحة العمل المتاحة لك",
            "description": "اختر المنطقة المناسبة من بطاقات الوصول أدناه.",
            "href": section_urls.get(first_section, ""),
            "label": "فتح مساحة العمل" if first_section else "",
        }

    cards = (
        {
            "key": "employees",
            "title": "الموظفون والقرارات",
            "description": "قائمة الموظفين وبيانات الخدمة والقرارات الوظيفية.",
            "detail": "إضافة موظف وسجل القرارات",
            "section": "employees",
            "permission": "hr.employees.view",
            "icon": "users",
            "color": "blue",
        },
        {
            "key": "workforce",
            "title": "المهام والتوزيع",
            "description": "المهام الميدانية وطلبات القوى العاملة والتكليفات والتغطية.",
            "detail": "متابعة الطلبات والتعارضات",
            "section": "workforce",
            "permission": ("hr.workforce.view", "hr.task.view"),
            "icon": "tasks",
            "color": "green",
        },
        {
            "key": "shifts",
            "title": "الورديات والحضور",
            "description": "قوالب الورديات والجدول اليومي وسجلات الحضور.",
            "detail": "التسجيل والمراجعة والتصحيح",
            "section": "shifts",
            "permission": ("hr.shift.view", "hr.attendance.view"),
            "icon": "calendar",
            "color": "orange",
        },
        {
            "key": "issues",
            "title": "المشكلات التشغيلية",
            "description": "تسجيل المشكلات ومتابعة المعالجة والمسؤوليات.",
            "detail": "قرارات الأعذار والإغلاق",
            "section": "issues",
            "permission": "hr.issue.view",
            "icon": "warning",
            "color": "purple",
        },
        {
            "key": "reports",
            "title": "التقارير والمؤشرات",
            "description": "التقارير المتاحة للموظفين والحضور والمشكلات.",
            "detail": "تفتح مساحة التقارير الحالية",
            "section": "issues",
            "permission": "hr.report.view",
            "icon": "chart",
            "color": "cyan",
        },
    )
    dashboard_cards = []
    for card in cards:
        allowed = _allowed_any(identity, *card["permission"]) if isinstance(
            card["permission"], tuple
        ) else _allowed(identity, card["permission"])
        displayed_card = dict(card)
        if card["key"] == "employees":
            actions = []
            if _allowed(identity, "hr.employees.create"):
                actions.append("إضافة موظف")
            if _allowed(identity, "hr.employment_records.manage"):
                actions.append("تسجيل قرار")
            displayed_card["detail"] = " و".join(actions) if actions else "عرض قائمة الموظفين"
        elif card["key"] == "workforce":
            areas = []
            if _allowed(identity, "hr.task.view"):
                areas.append("المهام الميدانية")
            if _allowed(identity, "hr.workforce.view"):
                areas.append("الطلبات والتكليفات")
            displayed_card["description"] = "، ".join(areas) if areas else card["description"]
            displayed_card["detail"] = (
                "التغطية والتعارضات بحسب الصلاحية"
                if _allowed(identity, "hr.workforce.view") else "عرض المهام الميدانية"
            )
        elif card["key"] == "shifts":
            if not _allowed(identity, "hr.shift.view"):
                displayed_card["description"] = "سجلات الحضور المتاحة ضمن نطاقك."
                displayed_card["detail"] = "التسجيل والمراجعة حسب الصلاحية"
        elif card["key"] == "issues":
            actions = []
            if _allowed(identity, "hr.issue.manage"):
                actions.append("تسجيل ومتابعة")
            if _allowed(identity, "hr.excuse.decide"):
                actions.append("قرارات الأعذار")
            if _allowed(identity, "hr.issue.close"):
                actions.append("الإغلاق")
            displayed_card["detail"] = "، ".join(actions) if actions else "عرض سجلات المشكلات"
        dashboard_cards.append({
            **displayed_card,
            "href": section_urls[card["section"]] if allowed else "",
            "available": allowed,
        })

    return {
        "metrics": metrics,
        "alerts": alerts,
        "recent_updates": recent_updates[:4],
        "next_action": next_action,
        "dashboard_cards": dashboard_cards,
        "dashboard_errors": bool(errors),
        "decisions_notice": (
            "لا تتوفر حالياً واجهة API مجمعة لعرض القرارات الإدارية القادمة."
            if _allowed(identity, "hr.employment_records.view") else
            "لا تتوفر صلاحية عرض سجل القرارات الإدارية."
        ),
    }


@require_http_methods(["GET", "POST"])
def home(request):
    client = ApiClient(token=request.session.get("access_token"))
    try:
        identity = client.get("/auth/me")
    except UnauthorizedException:
        return redirect("auth:login")
    except ApiException:
        return HttpResponse("تعذر التحقق من الهوية؛ حاول مجددًا", status=503)

    section = request.GET.get("section")
    if not section:
        section = "dashboard" if _can_view_dashboard(identity) else next(
            (name for name, _, permission in NAVIGATION if _allowed(identity, permission)),
            "dashboard",
        )
    if section not in dict((name, label) for name, label, _ in NAVIGATION):
        return HttpResponse("الصفحة المطلوبة غير موجودة", status=404)
    if not _can_view_section(identity, section):
        return HttpResponse("ليس لديك صلاحية الوصول إلى هذه الشاشة", status=403)
    title = dict((name, label) for name, label, _ in NAVIGATION)[section]
    error = success = ""
    if request.method == "POST":
        action = request.POST.get("action", "")
        permission = ACTION_PERMISSIONS.get(action)
        if action == "issue_transition":
            transition = request.POST.get("transition", "")
            permission = "hr.issue.close" if transition == "close" else "hr.excuse.decide" if transition in (
                "accept_excuse", "reject_excuse"
            ) else "hr.issue.manage"
        if not permission or not _allowed(identity, permission):
            return HttpResponse("ليس لديك صلاحية تنفيذ هذا الإجراء", status=403)
        try:
            endpoint, data = _post_data(request, action)
            if data.pop("_download", False):
                content, content_type, disposition = client.download(endpoint)
                response = HttpResponse(content, content_type=content_type)
                if disposition:
                    response["Content-Disposition"] = disposition
                return response
            client.post(endpoint, data)
            target = f"{reverse('hr:home')}?section={section}"
            if section == "shifts" and request.GET.get("view") == "attendance":
                target += "&view=attendance"
                if request.GET.get("business_date"):
                    target += f"&business_date={request.GET['business_date']}"
            return HttpResponseRedirect(target)
        except (ValueError, TypeError) as exc:
            error = str(exc) or "تحقق من قيم الحقول"
        except ForbiddenException:
            error = "ليس لديك صلاحية تنفيذ هذا الإجراء"
        except ApiException as exc:
            error = str(exc) or "تعذر تنفيذ العملية؛ أعد تحميل البيانات وحاول مجددًا"

    try:
        if section == "dashboard":
            dashboard = _dashboard_snapshot(client, identity, timezone.localdate().isoformat())
            datasets = []
            decision_screen = {}
            workforce_screen = {}
            workforce_requests_screen = {}
            assignments_screen = {}
            shifts_screen = {}
            attendance_screen = {}
            reports_screen = {}
        elif section == "reports":
            dashboard = {}
            datasets = []
            reports_screen = _reports_snapshot(client, identity, request)
            decision_screen = workforce_screen = workforce_requests_screen = assignments_screen = shifts_screen = attendance_screen = issue_screen = {}
        else:
            dashboard = {}
            datasets = _datasets(client, section) if section not in {"employees", "decisions", "issues"} else []
            employee_screen = _employee_snapshot(client, request) if section == "employees" else {}
            decision_screen = _decision_snapshot(client, request) if section == "decisions" else {}
            workforce_screen = _workforce_snapshot(client, request) if section == "workforce" else {}
            workforce_requests_screen = _workforce_requests_snapshot(client, request) if section == "workforce" and request.GET.get("view") == "requests" else {}
            assignments_screen = _assignments_snapshot(client, request) if section == "workforce" and request.GET.get("view") == "assignments" else {}
            shifts_screen = _shifts_snapshot(client, request) if section == "shifts" else {}
            attendance_screen = _attendance_snapshot(client, request) if section == "shifts" and request.GET.get("view") == "attendance" else {}
            issue_screen = _issue_snapshot(client, request) if section == "issues" else {}
            reports_screen = {}
    except UnauthorizedException:
        return redirect("auth:login")
    except ApiException:
        return HttpResponse("تعذر تحميل بيانات الموارد البشرية؛ حاول مجددًا", status=503)

    forms = {
        "employees": (
            {"action": "employee_create", "title": "إضافة موظف", "fields": (
                ("employee_no", "الرقم الوظيفي", "text", True), ("full_name", "الاسم الكامل", "text", True),
                ("phone", "الهاتف", "tel", False), ("home_unit_id", "معرف الإدارة", "text", True),
                ("position_title", "المسمى الوظيفي", "text", False), ("hire_date", "تاريخ التعيين", "date", False))},
            {"action": "decision_create", "title": "تسجيل قرار خدمة", "fields": (
                ("employee_id", "معرف الموظف", "text", True), ("change_type", "نوع القرار", "text", True),
                ("effective_date", "تاريخ السريان", "date", True), ("to_unit_id", "الإدارة المستهدفة", "text", False),
                ("to_position_title", "المسمى المستهدف", "text", False), ("reference_no", "مرجع القرار", "text", False),
                ("reason", "سبب القرار", "text", False))},
        ),
        "workforce": (
            {"action": "task_create", "title": "إنشاء مهمة", "fields": (
                ("task_no", "رقم المهمة", "text", True), ("title", "عنوان المهمة", "text", True),
                ("owner_unit_id", "الإدارة المالكة", "text", True), ("business_date", "التاريخ", "date", True),
                ("location_text", "الموقع", "text", False), ("description", "الوصف", "text", False))},
            {"action": "request_create", "title": "طلب احتياج", "fields": (
                ("request_no", "رقم الطلب", "text", True), ("requesting_unit_id", "الإدارة الطالبة", "text", True),
                ("requested_position", "المسمى المطلوب", "text", False), ("headcount", "العدد", "number", True),
                ("start_at", "من (ISO datetime)", "datetime-local", True), ("end_at", "إلى (ISO datetime)", "datetime-local", True),
                ("purpose", "الغرض", "text", True))},
            {"action": "assignment_create", "title": "إنشاء تكليف", "fields": (
                ("employee_id", "معرف الموظف", "text", True), ("beneficiary_unit_id", "الإدارة المستفيدة", "text", True),
                ("assignment_kind", "نوع التكليف", "text", True), ("business_date", "التاريخ", "date", True),
                ("start_at", "من (ISO datetime)", "datetime-local", False), ("end_at", "إلى (ISO datetime)", "datetime-local", False))},
            {"action": "task_transition", "title": "تحديث حالة مهمة", "fields": (
                ("entity_id", "معرف المهمة", "text", True), ("row_version", "إصدار السجل", "number", True),
                ("transition", "الإجراء (ready/start/complete/cancel/archive)", "text", True), ("reason", "السبب", "text", False))},
            {"action": "request_transition", "title": "إرسال أو رفض أو إغلاق طلب", "fields": (
                ("entity_id", "معرف الطلب", "text", True), ("row_version", "إصدار السجل", "number", True),
                ("transition", "الإجراء (submit/reject/close/cancel)", "text", True), ("reason", "السبب", "text", False))},
            {"action": "request_approve", "title": "اعتماد طلب احتياج", "fields": (
                ("entity_id", "معرف الطلب", "text", True), ("row_version", "إصدار السجل", "number", True))},
            {"action": "assignment_approve", "title": "اعتماد تكليف", "fields": (
                ("entity_id", "معرف التكليف", "text", True), ("row_version", "إصدار السجل", "number", True))},
        ),
        "shifts": (
            {"action": "template_create", "title": "إنشاء قالب وردية", "fields": (
                ("code", "رمز القالب", "text", True), ("name_ar", "اسم القالب", "text", True),
                ("start_local_time", "وقت البداية", "time", True), ("end_local_time", "وقت النهاية", "time", True),
                ("end_day_offset", "يوم النهاية (0 أو 1)", "number", True), ("break_minutes", "الاستراحة بالدقائق", "number", False),
                ("timezone_name", "المنطقة الزمنية", "text", True))},
            {"action": "roster_create", "title": "إضافة وردية للجدول", "fields": (
                ("employee_id", "معرف الموظف", "text", True), ("owner_unit_id", "الإدارة المالكة", "text", True),
                ("work_unit_id", "موقع العمل", "text", True), ("business_date", "تاريخ الوردية", "date", True),
                ("start_at", "البداية (ISO datetime)", "datetime-local", True), ("end_at", "النهاية (ISO datetime)", "datetime-local", True),
                ("timezone_name", "المنطقة الزمنية", "text", True), ("shift_name_snapshot", "اسم الوردية", "text", False))},
            {"action": "attendance_create", "title": "تسجيل حضور", "fields": (
                ("employee_id", "معرف الموظف", "text", True), ("attendance_kind", "النوع", "text", True),
                ("business_date", "التاريخ", "date", True), ("status", "الحالة", "text", True),
                ("shift_roster_id", "معرف الوردية", "text", False), ("notes", "ملاحظات", "text", False))},
            {"action": "attendance_approve", "title": "اعتماد حضور", "fields": (
                ("attendance_id", "معرف سجل الحضور", "text", True), ("row_version", "إصدار السجل", "number", True))},
            {"action": "attendance_submit", "title": "إرسال حضور للمراجعة", "fields": (
                ("attendance_id", "معرف سجل الحضور", "text", True), ("row_version", "إصدار السجل", "number", True))},
            {"action": "attendance_reject", "title": "رفض حضور", "fields": (
                ("attendance_id", "معرف سجل الحضور", "text", True), ("row_version", "إصدار السجل", "number", True),
                ("reason", "سبب الرفض", "text", True))},
            {"action": "attendance_correct", "title": "تصحيح حضور", "fields": (
                ("attendance_id", "معرف سجل الحضور", "text", True), ("row_version", "إصدار السجل", "number", True),
                ("status", "الحالة المصححة", "text", True), ("reason", "سبب التصحيح", "text", True))},
        ),
        "issues": (
            {"action": "issue_create", "title": "فتح مشكلة", "fields": (
                ("issue_type", "نوع المشكلة", "text", True), ("business_date", "التاريخ", "date", True),
                ("priority", "الأولوية", "text", True), ("reason", "الوصف", "text", True),
                ("employee_id", "معرف الموظف", "text", False), ("proposed_solution", "الحل المقترح", "text", False))},
            {"action": "issue_transition", "title": "تحديث حالة مشكلة", "fields": (
                ("issue_id", "معرف المشكلة", "text", True), ("row_version", "إصدار السجل", "number", True),
                ("transition", "الإجراء (start/resolve/close)", "text", True), ("resolution_notes", "نتيجة المعالجة", "text", False))},
            {"action": "report_export", "title": "تصدير تقرير CSV", "fields": (
                ("report_code", "التقرير (attendance/issues/employees)", "text", True),)},
        ),
    }
    visible_navigation = []
    for code, label, permission in NAVIGATION:
        if _can_view_section(identity, code):
            visible_navigation.append({
                "section": code, "label": label, "active": code == section,
            })
    visible_forms = [
        form for form in forms.get(section, ())
        if _allowed(identity, ACTION_PERMISSIONS[form["action"]])
    ]
    return render(request, "hr/home.html", {
        "page_title": title,
        "section": section,
        "navigation": visible_navigation,
        "datasets": datasets,
        "employee_screen": employee_screen if section == "employees" else {},
        "decision_screen": decision_screen if section == "decisions" else {},
        "workforce_screen": workforce_screen if section == "workforce" else {},
        "workforce_requests_screen": workforce_requests_screen if section == "workforce" else {},
        "assignments_screen": assignments_screen if section == "workforce" else {},
        "shifts_screen": shifts_screen if section == "shifts" else {},
        "attendance_screen": attendance_screen if section == "shifts" else {},
        "issue_screen": issue_screen if section == "issues" else {},
        "reports_screen": reports_screen if section == "reports" else {},
        "forms": visible_forms,
        "error": error,
        "success": success,
        "identity": identity,
        **dashboard,
    })


DETAIL_TABS = {
    "overview": "نظرة عامة",
    "basics": "البيانات الأساسية",
    "history": "التبعية والتاريخ الوظيفي",
    "decisions": "القرارات الإدارية",
    "assignments": "التكليفات والمهام",
    "attendance": "الورديات والحضور",
    "issues": "المشكلات التشغيلية",
}


def _detail_items(client, endpoint, params=None):
    try:
        response = client.get(endpoint, params=params or {})
    except ForbiddenException:
        return None
    except ApiException:
        return None
    if isinstance(response, list):
        return response
    return response.get("items", []) if isinstance(response, dict) else []


@require_http_methods(["GET"])
def employee_detail(request, employee_id):
    client = ApiClient(token=request.session.get("access_token"))
    try:
        UUID(str(employee_id))
        identity = client.get("/auth/me")
        employee = client.get(f"/hr/employees/{employee_id}")
    except UnauthorizedException:
        return redirect("auth:login")
    except (ForbiddenException, ApiException):
        return HttpResponse("ملف الموظف غير متاح ضمن نطاق الصلاحية", status=404)

    tab = request.GET.get("tab", "overview")
    if tab not in DETAIL_TABS:
        tab = "overview"
    as_of = request.GET.get("as_of", "").strip()
    if as_of:
        try:
            date.fromisoformat(as_of)
        except ValueError:
            as_of = ""
    employee_id_value = str(employee_id)
    needs_history = tab in {"overview", "history", "decisions"}
    history = _detail_items(
        client, f"/hr/employees/{employee_id}/employment-records",
        {"as_of": as_of} if as_of and needs_history else {},
    ) if needs_history else None
    assignments = _detail_items(client, "/hr/assignments", {"employee_id": employee_id_value}) \
        if tab in {"overview", "assignments"} else None
    roster = _detail_items(client, "/hr/shift-roster", {"employee_id": employee_id_value}) \
        if tab in {"overview", "attendance"} else None
    attendance = _detail_items(client, "/hr/attendance", {"employee_id": employee_id_value}) \
        if tab in {"overview", "attendance"} else None
    issues = _detail_items(client, "/hr/issues", {"employee_id": employee_id_value}) \
        if tab in {"overview", "issues"} else None
    permissions = set(identity.get("permissions", []))
    can_decide = "hr.employment_records.manage" in permissions
    if identity.get("is_admin"):
        can_decide = True
    status_labels = {"active": "نشط", "suspended": "موقوف", "terminated": "منتهية الخدمة"}
    return render(request, "hr/employee_detail.html", {
        "employee": employee,
        "employee_status_label": status_labels.get(employee.get("employment_status"), "غير متاح"),
        "tabs": [{"key": key, "label": label, "active": key == tab} for key, label in DETAIL_TABS.items()],
        "active_tab": tab,
        "history": history,
        "assignments": assignments,
        "roster": roster,
        "attendance": attendance,
        "issues": issues,
        "as_of": as_of,
        "can_decide": can_decide,
        "decision_endpoint": f"/hr/employees/{employee_id}/employment-records",
        "employee_id_value": employee_id_value,
    })
