from urllib.parse import urlencode

from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from shared.services.api_client import (
    ApiClient, ApiException, ConflictException, ForbiddenException,
    NotFoundException, UnauthorizedException, ValidationException,
)
from .forms import (
    MaintenanceCompletionForm, MaintenanceForm, MaintenancePlanForm,
    SafetyReleaseForm,
)
from .views import _can, _decorate_asset


TYPE_LABELS = {"preventive": "وقائية", "corrective": "تصحيحية", "emergency": "طارئة"}
STATUS_LABELS = {
    "open": "جديد", "in_progress": "قيد التنفيذ", "technically_completed": "بانتظار التحقق",
    "verified_closed": "مغلقة", "cancelled": "ملغاة",
}
BLOCK_LABELS = {"active": "مانع فعال", "released": "تم تحريره"}
PRIORITY_LABELS = {"high": "عالية", "medium": "متوسطة", "low": "منخفضة"}


def _failure(exc):
    if isinstance(exc, UnauthorizedException):
        return redirect("auth:login")
    status = 403 if isinstance(exc, ForbiddenException) else 404 if isinstance(exc, NotFoundException) else 422 if isinstance(exc, ValidationException) else 409 if isinstance(exc, ConflictException) else 503
    return HttpResponse({
        403: "ليس لديك صلاحية تنفيذ هذا الإجراء.",
        404: "السجل المطلوب غير متاح.",
        409: "تعذر تنفيذ الإجراء بسبب تعارض في حالة السجل.",
        422: "تحقق من البيانات ثم أعد المحاولة.",
        503: "تعذر الاتصال بخدمة المعدات، حاول مجدداً.",
    }[status], status=status)


def _decorate_order(row, assets):
    item = dict(row)
    asset = assets.get(str(item.get("asset_id")), {})
    item["asset_name"] = asset.get("asset_name", item.get("asset_id", "—"))
    item["asset_code"] = asset.get("asset_code", "")
    item["maintenance_type_label"] = TYPE_LABELS.get(item.get("maintenance_type"), item.get("maintenance_type", "—"))
    item["status_label"] = STATUS_LABELS.get(item.get("status"), item.get("status", "—"))
    item["block_status_label"] = BLOCK_LABELS.get(item.get("block_status"), "—")
    item["priority_label"] = PRIORITY_LABELS.get(item.get("priority"), item.get("priority", "—"))
    item["is_active_block"] = item.get("block_status") == "active"
    return item


@require_http_methods(["GET", "POST"])
def equipment_maintenance(request):
    client = ApiClient(token=request.session.get("access_token"))
    try:
        identity = client.get("/auth/me")
    except (UnauthorizedException, ForbiddenException, NotFoundException, ValidationException, ConflictException, ApiException) as exc:
        return _failure(exc)

    can_view = _can(identity, "equipment.maintenance.view")
    can_create = _can(identity, "equipment.maintenance.create")
    can_execute = _can(identity, "equipment.maintenance.execute")
    can_release = _can(identity, "equipment.safety.release")
    if not (can_view or can_create):
        return HttpResponse("ليس لديك صلاحية عرض الصيانة.", status=403)

    action = request.POST.get("action", "") if request.method == "POST" else ""
    try:
        raw_assets = client.get("/equipment/assets", {"skip": 0, "limit": 200, "sort_by": "asset_code", "sort_dir": "asc"}).get("items", [])
        raw_orders = client.get("/equipment/maintenance-orders").get("items", []) if can_view else []
        raw_plans = client.get("/equipment/maintenance-plans").get("items", []) if can_view else []
        raw_due = client.get("/equipment/maintenance-plans/due").get("items", []) if can_view else []
        raw_inspections = client.get("/equipment/inspections").get("items", []) if can_release else []
    except (UnauthorizedException, ForbiddenException, NotFoundException, ValidationException, ConflictException, ApiException) as exc:
        return _failure(exc)

    assets = [_decorate_asset(row, identity) for row in raw_assets]
    asset_map = {str(row["id"]): row for row in assets}
    orders = [_decorate_order(row, asset_map) for row in raw_orders]
    search = request.GET.get("search", "").strip().lower()
    asset_filter = request.GET.get("asset_id", "").strip()
    status_filter = request.GET.get("status", "").strip()
    type_filter = request.GET.get("maintenance_type", "").strip()
    priority_filter = request.GET.get("priority", "").strip()
    filtered = orders
    if search:
        filtered = [row for row in filtered if search in f"{row['order_code']} {row['asset_name']} {row['asset_code']} {row.get('description', '')}".lower()]
    if asset_filter:
        filtered = [row for row in filtered if str(row.get("asset_id")) == asset_filter]
    if status_filter:
        filtered = [row for row in filtered if row.get("status") == status_filter]
    if type_filter:
        filtered = [row for row in filtered if row.get("maintenance_type") == type_filter]
    if priority_filter:
        filtered = [row for row in filtered if row.get("priority") == priority_filter]

    selected_id = request.GET.get("order_id", "").strip()
    selected = next((row for row in orders if str(row.get("id")) == selected_id), None)
    maintenance_form = MaintenanceForm(
        request.POST if action == "create_maintenance" else None,
        assets=assets,
        initial={"asset_id": request.GET.get("asset_id", "")} if request.GET.get("asset_id") else None,
    )
    plan_form = MaintenancePlanForm(request.POST if action == "create_plan" else None, assets=assets)
    completion_form = MaintenanceCompletionForm(request.POST if action == "complete_order" else None)
    release_form = SafetyReleaseForm(request.POST if action == "release_order" else None, inspections=raw_inspections)
    error_message = None

    if action == "create_maintenance":
        if not can_create:
            return HttpResponse("ليس لديك صلاحية إنشاء أمر صيانة.", status=403)
        if maintenance_form.is_valid():
            try:
                created = client.post("/equipment/maintenance-orders", maintenance_form.payload())
                return redirect(f"{request.path}?order_id={created.get('id', '')}&saved=order")
            except (UnauthorizedException, ForbiddenException, NotFoundException, ValidationException, ConflictException, ApiException) as exc:
                error_message = str(exc)
    elif action == "create_plan":
        if not can_create:
            return HttpResponse("ليس لديك صلاحية إنشاء خطة صيانة.", status=403)
        if plan_form.is_valid():
            try:
                client.post("/equipment/maintenance-plans", plan_form.payload())
                return redirect(f"{request.path}?saved=plan")
            except (UnauthorizedException, ForbiddenException, NotFoundException, ValidationException, ConflictException, ApiException) as exc:
                error_message = str(exc)
    elif action == "generate_order":
        if not can_create:
            return HttpResponse("ليس لديك صلاحية إنشاء أمر صيانة.", status=403)
        try:
            client.post(f"/equipment/maintenance-plans/{request.POST.get('plan_id')}/orders", {})
            return redirect(f"{request.path}?saved=order")
        except (UnauthorizedException, ForbiddenException, NotFoundException, ValidationException, ConflictException, ApiException) as exc:
            error_message = str(exc)
    elif action in {"pause_plan", "resume_plan"}:
        if not can_create:
            return HttpResponse("ليس لديك صلاحية إدارة خطط الصيانة.", status=403)
        suffix = "pause" if action == "pause_plan" else "resume"
        try:
            client.post(f"/equipment/maintenance-plans/{request.POST.get('plan_id')}/{suffix}", {})
            return redirect(f"{request.path}?saved=plan")
        except (UnauthorizedException, ForbiddenException, NotFoundException, ValidationException, ConflictException, ApiException) as exc:
            error_message = str(exc)
    elif action == "complete_order":
        if not can_execute:
            return HttpResponse("ليس لديك صلاحية تسجيل إكمال الصيانة.", status=403)
        if completion_form.is_valid():
            try:
                client.post(f"/equipment/maintenance-orders/{request.POST.get('order_id')}/complete", completion_form.payload())
                return redirect(f"{request.path}?order_id={request.POST.get('order_id')}&saved=complete")
            except (UnauthorizedException, ForbiddenException, NotFoundException, ValidationException, ConflictException, ApiException) as exc:
                error_message = str(exc)
    elif action == "release_order":
        if not can_release:
            return HttpResponse("ليس لديك صلاحية تحرير مانع الصيانة.", status=403)
        if release_form.is_valid():
            try:
                client.post(f"/equipment/maintenance-orders/{request.POST.get('order_id')}/release-block", release_form.payload())
                return redirect(f"{request.path}?order_id={request.POST.get('order_id')}&saved=released")
            except (UnauthorizedException, ForbiddenException, NotFoundException, ValidationException, ConflictException, ApiException) as exc:
                error_message = str(exc)

    paginator = Paginator(filtered, 8)
    page_obj = paginator.get_page(request.GET.get("page", 1))
    active_blocks = [row for row in orders if row.get("block_status") == "active"]
    if selected:
        release_form = SafetyReleaseForm(inspections=raw_inspections)
    query = {key: value for key, value in {"search": search, "asset_id": asset_filter, "status": status_filter, "maintenance_type": type_filter, "priority": priority_filter}.items() if value}
    return render(request, "equipment/maintenance.html", {
        "identity": identity, "assets": assets, "orders": page_obj.object_list, "page_obj": page_obj,
        "selected_order": selected, "due_plans": raw_due, "plans": raw_plans, "active_blocks": active_blocks,
        "maintenance_form": maintenance_form, "plan_form": plan_form, "completion_form": completion_form,
        "release_form": release_form, "error_message": error_message, "can_create": can_create,
        "can_execute": can_execute, "can_release": can_release, "open_form": request.GET.get("mode") == "create",
        "open_plan": request.GET.get("mode") == "plan", "saved": request.GET.get("saved"), "query": urlencode(query),
        "new_count": sum(row.get("status") == "open" for row in orders),
        "in_progress_count": sum(row.get("status") == "in_progress" for row in orders),
        "due_count": len(raw_due), "verification_count": sum(row.get("status") == "technically_completed" for row in orders),
        "block_count": len(active_blocks),
    })
