import csv
from datetime import date
from decimal import Decimal, InvalidOperation
from uuid import uuid4

from django.http import HttpResponse
from django.shortcuts import redirect, render

from shared.services.api_client import (
    ApiClient,
    ApiException,
    ForbiddenException,
    NotFoundException,
    UnauthorizedException,
)


STATUS_LABELS = {
    "planned": "مخطط", "ready": "جاهز", "in_progress": "قيد التنفيذ",
    "blocked": "متعثر", "completed": "مكتمل", "closed": "مغلق",
}
PLAN_STATUS_LABELS = {
    "draft": "مسودة", "ready_for_commitment": "جاهز للاعتماد", "committed": "معتمد",
    "in_progress": "قيد التنفيذ", "closed": "مغلق", "reopened": "معاد الفتح", "cancelled": "ملغى",
}
READINESS_LABELS = {
    "not_ready": "غير جاهز", "ready": "جاهز", "warnings": "جاهزية مع ملاحظات",
}
ALLOWED_STATUS = {
    "planned": ("ready", "blocked"), "ready": ("in_progress", "blocked"),
    "in_progress": ("completed", "blocked"), "blocked": ("ready", "in_progress"),
    "completed": ("closed",), "closed": (),
}


def _decimal(value):
    try:
        return Decimal(str(value or "0"))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def _display(value, unavailable=False):
    return "غير متاح" if unavailable or value is None or value == "" else str(value)


def _project_rows(client):
    return client.get("/pm/ui-projects", params={"section": "work-orders"}).get("items", [])


def _selected_project(projects, project_id):
    normalized = str(project_id or "").replace("-", "").lower()
    return next((row for row in projects if str(row.get("id", "")).replace("-", "").lower() == normalized), None)


def _safe_id(value):
    return str(value).strip() if value and str(value).strip() else None


def _post_action(client, request, project_id):
    action = request.POST.get("action", "")
    plan_id = _safe_id(request.POST.get("plan_id"))
    item_id = _safe_id(request.POST.get("item_id"))
    root = f"/daily-work/projects/{project_id}"
    if action == "create_plan":
        start = request.POST.get("period_start") or request.POST.get("plan_date")
        end = request.POST.get("period_end") or start
        data = {"plan_date": request.POST.get("plan_date"), "period_start": start, "period_end": end}
        if _safe_id(request.POST.get("owner_user_id")):
            data["owner_user_id"] = request.POST["owner_user_id"]
        result = client.post(root + "/plans", data=data)
        return result.get("id")
    if action == "add_item" and plan_id:
        data = {
            "work_date": request.POST.get("work_date"), "title": request.POST.get("title"),
            "target_quantity": request.POST.get("target_quantity") or "0",
            "planned_minutes": request.POST.get("planned_minutes") or "0",
            "unit": request.POST.get("unit") or "", "source_type": request.POST.get("source_type") or "pm_activity",
            "team_name": request.POST.get("team_name") or "", "shift": request.POST.get("shift") or "",
            "location": request.POST.get("location") or "", "notes": request.POST.get("notes") or "",
            "emergency_flag": request.POST.get("emergency_flag") == "on",
            "emergency_reason": request.POST.get("emergency_reason") or "",
        }
        for key in ("activity_id", "work_order_id", "assignee_user_id"):
            value = _safe_id(request.POST.get(key))
            if value:
                data[key] = value
        result = client.post(root + f"/plans/{plan_id}/items", data=data)
        return result.get("item", {}).get("id") or result.get("id")
    if action == "estimate" and item_id:
        client.post(root + f"/items/{item_id}/estimates", data={
            "estimate_kind": request.POST.get("estimate_kind") or "labor",
            "quantity": request.POST.get("estimate_quantity") or "0", "unit": request.POST.get("estimate_unit") or "lot",
            "unit_rate": request.POST.get("unit_rate") or "0", "currency_id": request.POST.get("currency_id") or "USD",
            "fx_rate": request.POST.get("fx_rate") or "1", "fx_as_of": request.POST.get("fx_as_of") or date.today().isoformat(),
            "confidence": request.POST.get("confidence") or "medium",
        })
    elif action == "commit" and plan_id:
        client.post(root + f"/plans/{plan_id}/commit")
    elif action == "close" and plan_id:
        client.post(root + f"/plans/{plan_id}/close", data={"summary": request.POST.get("summary") or "", "idempotency_key": "dw03-close-" + uuid4().hex})
    elif action == "reopen" and plan_id:
        client.post(root + f"/plans/{plan_id}/reopen", data={"reason": request.POST.get("reason") or "إعادة فتح الخطة للمراجعة", "idempotency_key": "dw03-reopen-" + uuid4().hex})
    elif action == "status" and item_id:
        client.post(root + f"/items/{item_id}/status", data={"status": request.POST.get("status")})
    elif action == "readiness" and item_id:
        client.post(root + f"/items/{item_id}/readiness", data={"check_type": request.POST.get("check_type") or "general", "result": request.POST.get("result") or "ready", "note": request.POST.get("note") or ""})
    elif action == "actual" and item_id:
        client.post(root + f"/items/{item_id}/updates", data={"event_type": request.POST.get("event_type") or "quantity", "value": request.POST.get("actual_value") or "0", "unit": request.POST.get("actual_unit") or "", "currency_id": _safe_id(request.POST.get("actual_currency")), "fx_rate": request.POST.get("actual_fx_rate") or "1", "idempotency_key": "dw03-actual-" + uuid4().hex, "note": request.POST.get("actual_note") or ""})
    elif action == "blocker" and item_id:
        client.post(root + f"/items/{item_id}/blockers", data={"blocker_type": request.POST.get("blocker_type") or "general", "description": request.POST.get("description") or "عائق غير موصوف"})
    elif action == "resolve" and item_id and _safe_id(request.POST.get("blocker_id")):
        client.post(root + f"/items/{item_id}/blockers/{request.POST['blocker_id']}/resolve", data={"note": request.POST.get("note") or "تمت المعالجة"})
    elif action == "assign" and item_id:
        client.post(root + f"/items/{item_id}/assignments", data={
            "subject_type": request.POST.get("subject_type") or "user",
            "subject_id": request.POST.get("subject_id") or "",
            "role": request.POST.get("role") or "worker",
            "is_lead": request.POST.get("is_lead") == "on",
            "planned_minutes": request.POST.get("assignment_minutes") or "0",
        })
    return item_id or plan_id


def _load_context(client, selected_id, work_date, plan_id=None, item_id=None):
    projects = _project_rows(client)
    selected = _selected_project(projects, selected_id) or (projects[0] if projects else None)
    if not selected:
        return {"projects": [], "selected_project": None, "work_date": work_date, "plans": [], "items": [], "summary": {}}
    project_id = str(selected["id"])
    items = client.get(f"/daily-work/projects/{project_id}/items", params={"work_date": work_date}).get("items", [])
    schema_ready = True
    try:
        plans = client.get(f"/daily-work/projects/{project_id}/plans", params={"plan_date": work_date}).get("plans", [])
    except ApiException:
        # Production databases are not upgraded by DW-03. Keep the legacy board
        # readable and expose the gate instead of silently treating plans as empty.
        plans = []
        schema_ready = False
    refs = client.get(f"/pm/projects/{project_id}/ui-references", params={"section": "work-orders"})
    chosen_plan = next((p for p in plans if str(p.get("id")) == str(plan_id)), None) if plan_id else None
    chosen_plan = chosen_plan or (plans[0] if plans else None)
    chosen_item = next((i for i in items if str(i.get("id")) == str(item_id)), None) if item_id else None
    metrics = client.get(f"/daily-work/projects/{project_id}/items/{chosen_item['id']}/metrics") if chosen_item else None
    assignments = client.get(f"/daily-work/projects/{project_id}/items/{chosen_item['id']}/assignments").get("assignments", []) if chosen_item else []
    control = client.get(f"/daily-work/projects/{project_id}/plans/{chosen_plan['id']}/control") if chosen_plan else None
    for item in items:
        item["status_label"] = STATUS_LABELS.get(item.get("status"), item.get("status", "غير محدد"))
        item["source_label"] = "عمل مستقل" if item.get("source_type") == "independent" else "مصدر خارجي"
        unit = f" {item.get('unit')}" if item.get("unit") else ""
        item["target_display"] = _display(item.get("target_quantity")) + unit
        item["actual_display"] = _display(item.get("actual_quantity")) + unit
        item["remaining_display"] = _display(item.get("remaining_quantity")) + unit
        item["estimated_cost_display"] = _display(item.get("estimate_total"), item.get("estimated_cost_status") == "unavailable")
    selected_status = chosen_item.get("status") if chosen_item else None
    allowed_statuses = [{"value": value, "label": STATUS_LABELS[value]} for value in ALLOWED_STATUS.get(selected_status, ())]
    total = len(items)
    completed = sum(item.get("status") in ("completed", "closed") for item in items)
    target = sum((_decimal(item.get("target_quantity")) for item in items), Decimal("0"))
    actual = sum((_decimal(item.get("actual_quantity")) for item in items), Decimal("0"))
    return {
        "projects": projects, "selected_project": selected, "work_date": work_date, "plans": plans,
        "selected_plan": chosen_plan, "items": items, "selected_item": chosen_item, "metrics": metrics,
        "assignments": assignments, "control": control,
        "references": refs, "status_labels": STATUS_LABELS, "plan_status_labels": PLAN_STATUS_LABELS,
        "readiness_labels": READINESS_LABELS, "allowed_statuses": allowed_statuses,
        "schema_ready": schema_ready,
        "summary": {"total": total, "completed": completed, "in_progress": sum(i.get("status") == "in_progress" for i in items), "blocked": sum(i.get("status") == "blocked" for i in items), "target": target, "actual": actual, "completion_percent": round(completed * 100 / total) if total else 0},
    }


def index(request):
    client = ApiClient(token=request.session.get("access_token"))
    work_date = request.POST.get("work_date") or request.GET.get("daily_date") or date.today().isoformat()
    selected_id = request.POST.get("project_id") or request.GET.get("project_id")
    plan_id = request.POST.get("plan_id") or request.GET.get("plan_id")
    item_id = request.POST.get("item_id") or request.GET.get("item_id")
    try:
        if request.method == "POST":
            result_id = _post_action(client, request, selected_id)
            item_action = request.POST.get("action") in {"status", "readiness", "actual", "blocker", "resolve", "estimate", "assign"}
            target_plan = plan_id or (result_id if request.POST.get("action") in {"create_plan", "commit", "close", "reopen"} else "")
            target_item = result_id if item_action else (result_id if request.POST.get("action") == "add_item" else item_id or "")
            return redirect(f"/daily-work/?project_id={selected_id}&daily_date={work_date}&plan_id={target_plan or ''}&item_id={target_item}")
        return render(request, "daily_work/index_v2.html", _load_context(client, selected_id, work_date, plan_id, item_id))
    except UnauthorizedException:
        return redirect("auth:login")
    except ForbiddenException:
        return HttpResponse("لا تملك صلاحية الوصول إلى العمل اليومي", status=403)
    except (NotFoundException, ApiException) as exc:
        try:
            context = _load_context(client, selected_id, work_date, plan_id, item_id)
        except Exception:
            context = {"projects": [], "items": [], "plans": [], "work_date": work_date}
        context["error"] = str(exc)
        return render(request, "daily_work/index_v2.html", context, status=409 if request.method == "POST" else 503)


def reporting(request):
    client = ApiClient(token=request.session.get("access_token"))
    work_date = request.GET.get("daily_date") or date.today().isoformat()
    try:
        context = _load_context(client, request.GET.get("project_id"), work_date, request.GET.get("plan_id"), request.GET.get("item_id"))
        if request.GET.get("download") == "csv":
            response = HttpResponse(content_type="text/csv; charset=utf-8-sig")
            response["Content-Disposition"] = f'attachment; filename="daily-work-{work_date}.csv"'
            writer = csv.writer(response)
            writer.writerow(["التاريخ", "العمل", "المصدر", "المستهدف", "الفعلي", "المتبقي", "الحالة"])
            writer.writerows([[work_date, i.get("title"), i.get("source_label"), i.get("target_display"), i.get("actual_display"), i.get("remaining_display"), i.get("status_label")] for i in context["items"]])
            return response
        return render(request, "daily_work/report.html", context)
    except UnauthorizedException:
        return redirect("auth:login")
    except ForbiddenException:
        return HttpResponse("لا تملك صلاحية عرض تقرير العمل اليومي", status=403)
    except ApiException as exc:
        return HttpResponse(str(exc), status=503)
