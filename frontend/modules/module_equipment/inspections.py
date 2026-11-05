from datetime import datetime
from urllib.parse import urlencode

from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from shared.services.api_client import (
    ApiClient, ApiException, ConflictException, ForbiddenException,
    NotFoundException, UnauthorizedException, ValidationException,
)
from .forms import InspectionForm, MaintenanceForm, SafetyReleaseForm
from .views import _can, _decorate_asset


TYPE_LABELS = {
    "pre_operation": "قبل التشغيل",
    "post_repair": "بعد الإصلاح",
    "periodic": "دوري",
    "return": "عند الإرجاع",
}
RESULT_LABELS = {"passed": "سليم", "conditional": "مشروط", "failed": "غير سليم"}
STATUS_LABELS = {"submitted": "بانتظار المراجعة", "verified": "تم التحقق"}
BLOCK_LABELS = {"active": "مانع فعال", "released": "تم التحرير"}


def _failure(exc):
    if isinstance(exc, UnauthorizedException):
        return redirect("auth:login")
    status = 403 if isinstance(exc, ForbiddenException) else 404 if isinstance(exc, NotFoundException) else 422 if isinstance(exc, ValidationException) else 409 if isinstance(exc, ConflictException) else 503
    messages = {
        403: "ليس لديك صلاحية تنفيذ هذا الإجراء.",
        404: "السجل المطلوب غير متاح.",
        409: "تعذر تنفيذ الإجراء بسبب تعارض في حالة السجل.",
        422: "تحقق من بيانات الفحص ثم أعد المحاولة.",
        503: "تعذر الاتصال بخدمة المعدات، حاول مجدداً.",
    }
    return HttpResponse(messages[status], status=status)


def _date(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except (TypeError, ValueError):
        return None


def _decorate_inspection(row, assets):
    item = dict(row)
    asset = assets.get(str(item.get("asset_id")), {})
    item["asset_name"] = asset.get("asset_name", item.get("asset_id", "—"))
    item["asset_code"] = asset.get("asset_code", "")
    item["inspection_type_label"] = TYPE_LABELS.get(item.get("inspection_type"), item.get("inspection_type", "—"))
    item["result_label"] = RESULT_LABELS.get(item.get("result"), item.get("result", "—"))
    item["status_label"] = STATUS_LABELS.get(item.get("status"), item.get("status", "—"))
    item["block_status_label"] = BLOCK_LABELS.get(item.get("block_status"), "—")
    item["is_active_block"] = item.get("block_status") == "active"
    return item


@require_http_methods(["GET", "POST"])
def equipment_inspections(request):
    client = ApiClient(token=request.session.get("access_token"))
    try:
        identity = client.get("/auth/me")
    except (UnauthorizedException, ForbiddenException, NotFoundException, ValidationException, ConflictException, ApiException) as exc:
        return _failure(exc)
    if not _can(identity, "equipment.inspections.view"):
        return HttpResponse("ليس لديك صلاحية عرض الفحوصات.", status=403)

    can_record = _can(identity, "equipment.inspections.record")
    can_verify = _can(identity, "equipment.inspections.verify")
    can_maintenance_view = _can(identity, "equipment.maintenance.view")
    can_maintenance_create = _can(identity, "equipment.maintenance.create")
    can_release = _can(identity, "equipment.safety.release")
    try:
        assets_result = client.get("/equipment/assets", {"skip": 0, "limit": 200, "sort_by": "asset_code", "sort_dir": "asc"})
        raw_assets = assets_result.get("items", [])
        raw_inspections = client.get("/equipment/inspections").get("items", [])
        raw_orders = client.get("/equipment/maintenance-orders").get("items", []) if can_maintenance_view else []
    except (UnauthorizedException, ForbiddenException, NotFoundException, ValidationException, ConflictException, ApiException) as exc:
        return _failure(exc)

    assets = [_decorate_asset(row, identity) for row in raw_assets]
    asset_map = {str(row["id"]): row for row in assets}
    inspections = [_decorate_inspection(row, asset_map) for row in raw_inspections]
    search = request.GET.get("search", "").strip().lower()
    asset_filter = request.GET.get("asset_id", "").strip()
    type_filter = request.GET.get("inspection_type", "").strip()
    result_filter = request.GET.get("result", "").strip()
    status_filter = request.GET.get("status", "").strip()
    from_filter = request.GET.get("from", "").strip()
    to_filter = request.GET.get("to", "").strip()
    from_date, to_date = _date(from_filter), _date(to_filter)
    filtered = inspections
    if search:
        filtered = [row for row in filtered if search in f"{row['asset_name']} {row['asset_code']}".lower()]
    if asset_filter:
        filtered = [row for row in filtered if str(row.get("asset_id")) == asset_filter]
    if type_filter:
        filtered = [row for row in filtered if row.get("inspection_type") == type_filter]
    if result_filter:
        filtered = [row for row in filtered if row.get("result") == result_filter]
    if status_filter:
        filtered = [row for row in filtered if row.get("status") == status_filter]
    if from_date:
        filtered = [row for row in filtered if (_date(row.get("inspected_at")) or from_date) >= from_date]
    if to_date:
        filtered = [row for row in filtered if (_date(row.get("inspected_at")) or to_date) <= to_date]

    selected_id = request.GET.get("inspection_id", "").strip()
    selected = next((row for row in inspections if str(row.get("id")) == selected_id), None)
    action = request.POST.get("action", "") if request.method == "POST" else ""
    inspection_form = InspectionForm(
        request.POST if action == "create_inspection" else None,
        assets=assets,
        initial={"asset_id": request.GET.get("asset_id", "")} if request.GET.get("asset_id") else None,
    )
    maintenance_form = MaintenanceForm(request.POST if action == "create_maintenance" else None, assets=assets)
    release_form = SafetyReleaseForm(request.POST if action == "release_block" else None, inspections=raw_inspections)
    error_message = None
    if action == "create_inspection":
        if not can_record:
            return HttpResponse("ليس لديك صلاحية تسجيل الفحص.", status=403)
        if inspection_form.is_valid():
            try:
                client.post("/equipment/inspections", inspection_form.payload())
                return redirect(f"{request.path}?saved=inspection")
            except (UnauthorizedException, ForbiddenException, NotFoundException, ValidationException, ConflictException, ApiException) as exc:
                error_message = str(exc)
    elif action == "create_maintenance":
        if not can_maintenance_create:
            return HttpResponse("ليس لديك صلاحية إنشاء أمر صيانة.", status=403)
        if maintenance_form.is_valid():
            try:
                client.post("/equipment/maintenance-orders", maintenance_form.payload())
                return redirect(f"{request.path}?saved=maintenance")
            except (UnauthorizedException, ForbiddenException, NotFoundException, ValidationException, ConflictException, ApiException) as exc:
                error_message = str(exc)
    elif action == "verify_inspection":
        if not can_verify:
            return HttpResponse("ليس لديك صلاحية اعتماد الفحص.", status=403)
        try:
            client.post(f"/equipment/inspections/{request.POST.get('inspection_id')}/verify", {})
            return redirect(f"{request.path}?inspection_id={request.POST.get('inspection_id')}&verified=1")
        except (UnauthorizedException, ForbiddenException, NotFoundException, ValidationException, ConflictException, ApiException) as exc:
            error_message = str(exc)
    elif action == "release_block":
        if not can_release:
            return HttpResponse("ليس لديك صلاحية تحرير مانع التشغيل.", status=403)
        if release_form.is_valid():
            try:
                client.post(f"/equipment/inspections/{request.POST.get('blocked_inspection_id')}/release-block", release_form.payload())
                return redirect(f"{request.path}?inspection_id={request.POST.get('blocked_inspection_id')}&released=1")
            except (UnauthorizedException, ForbiddenException, NotFoundException, ValidationException, ConflictException, ApiException) as exc:
                error_message = str(exc)

    paginator = Paginator(filtered, 8)
    page_obj = paginator.get_page(request.GET.get("page", 1))
    active_blocks = [row for row in inspections if row.get("block_status") == "active"]
    active_blocks.extend({
        "id": row.get("id"), "asset_id": row.get("asset_id"), "asset_name": asset_map.get(str(row.get("asset_id")), {}).get("asset_name", "—"),
        "asset_code": asset_map.get(str(row.get("asset_id")), {}).get("asset_code", ""), "reason": row.get("description") or row.get("reason") or "أمر صيانة مفتوح", "source": "maintenance",
        "created_at": row.get("created_at"), "block_status": row.get("block_status"), "is_active_block": True,
    } for row in raw_orders if row.get("block_status") == "active")
    actor = str(identity.get("id") or identity.get("user_id") or "").replace("-", "").lower()
    if selected:
        selected["can_verify"] = can_verify and selected.get("status") == "submitted" and str(selected.get("created_by", "")).replace("-", "").lower() != actor
        release_form = SafetyReleaseForm(inspections=raw_inspections)

    query = {key: value for key, value in {"search": search, "asset_id": asset_filter, "inspection_type": type_filter, "result": result_filter, "status": status_filter, "from": from_filter, "to": to_filter}.items() if value}
    return render(request, "equipment/inspections.html", {
        "identity": identity, "assets": assets, "page_obj": page_obj, "inspections": page_obj.object_list,
        "selected_inspection": selected, "active_blocks": active_blocks, "inspection_form": inspection_form,
        "maintenance_form": maintenance_form, "release_form": release_form, "error_message": error_message,
        "can_record": can_record, "can_verify": can_verify, "can_maintenance_create": can_maintenance_create, "can_release": can_release,
        "due_count": 0, "pending_count": sum(row.get("status") == "submitted" for row in inspections),
        "blocked_count": len(active_blocks), "completed_count": sum(row.get("status") == "verified" for row in inspections),
        "query": urlencode(query), "saved": request.GET.get("saved"), "verified": request.GET.get("verified"), "released": request.GET.get("released"),
        "open_form": request.GET.get("mode") == "create", "open_maintenance": request.GET.get("mode") == "maintenance",
    })
