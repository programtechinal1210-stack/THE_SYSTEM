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
from .forms import MeterEventForm
from .views import _can, _decorate_asset


EVENT_LABELS = {"reading": "قراءة جديدة", "replacement": "استبدال عداد", "correction": "تصحيح قراءة"}
STATUS_LABELS = {"approved": "معتمد", "pending": "بانتظار الاعتماد"}


def _error(exc):
    if isinstance(exc, UnauthorizedException):
        return redirect("auth:login")
    status = 403 if isinstance(exc, ForbiddenException) else 404 if isinstance(exc, NotFoundException) else 422 if isinstance(exc, ValidationException) else 409 if isinstance(exc, ConflictException) else 503
    messages = {403: "ليس لديك صلاحية الوصول إلى العدادات ضمن نطاقك", 404: "السجل المطلوب غير متاح", 409: "تعذر تنفيذ الإجراء بسبب تعارض في حالة العداد", 422: "تحقق من بيانات القراءة ثم أعد المحاولة", 503: "تعذر تحميل خدمة العدادات؛ حاول مجددًا"}
    return HttpResponse(messages[status], status=status)


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


@require_http_methods(["GET", "POST"])
def equipment_meters(request):
    client = ApiClient(token=request.session.get("access_token"))
    try:
        identity = client.get("/auth/me")
    except (UnauthorizedException, ForbiddenException, NotFoundException, ValidationException, ConflictException, ApiException) as exc:
        if isinstance(exc, ValidationException):
            return HttpResponse("تعذر تحميل هوية المستخدم من خدمة المصادقة", status=422)
        return _error(exc)
    if not _can(identity, "equipment.meters.view"):
        return HttpResponse("ليس لديك صلاحية عرض العدادات", status=403)
    try:
        result = client.get("/equipment/assets", {"skip": 0, "limit": 200, "sort_by": "asset_code", "sort_dir": "asc"})
    except (UnauthorizedException, ForbiddenException, NotFoundException, ValidationException, ConflictException, ApiException) as exc:
        if isinstance(exc, ValidationException):
            return HttpResponse("تعذر تحميل قائمة المعدات؛ تحقق من عقد خدمة المعدات", status=422)
        return _error(exc)

    all_assets = [_decorate_asset(row, identity) for row in result.get("items", []) if row.get("meter_type_locked") not in (None, "none")]
    search, meter_type = request.GET.get("search", "").strip().lower(), request.GET.get("meter_type", "").strip()
    location, status_filter = request.GET.get("location", "").strip(), request.GET.get("status", "").strip()
    start_filter, end_filter = request.GET.get("from", "").strip(), request.GET.get("to", "").strip()
    start_at, end_at = _parse_date(start_filter), _parse_date(end_filter)
    assets = all_assets
    if search:
        assets = [a for a in assets if search in f"{a.get('asset_name', '')} {a.get('asset_code', '')}".lower()]
    if meter_type:
        assets = [a for a in assets if a.get("meter_type_locked") == meter_type]
    if location:
        assets = [a for a in assets if a.get("current_location") == location]

    selected_id = request.GET.get("asset_id", "").strip()
    selected = next((a for a in assets if str(a.get("id")) == selected_id), assets[0] if assets else None)
    events = []
    if selected:
        try:
            events = client.get(f"/equipment/assets/{selected['id']}/meter-events").get("items", [])
        except (UnauthorizedException, ForbiddenException, NotFoundException, ValidationException, ConflictException, ApiException) as exc:
            return _error(exc)

    actor = str(identity.get("id") or identity.get("user_id") or "").replace("-", "").lower()
    for event in events:
        event["event_type_label"] = EVENT_LABELS.get(event.get("event_type"), "حدث عداد")
        event["status_label"] = STATUS_LABELS.get(event.get("status"), event.get("status", "—"))
        event["can_approve"] = _can(identity, "equipment.meters.approve") and event.get("status") == "pending" and str(event.get("created_by", "")).replace("-", "").lower() != actor
    visible_events = events
    if status_filter in {"pending", "approved"}:
        visible_events = [e for e in visible_events if e.get("status") == status_filter]
    if start_at:
        visible_events = [e for e in visible_events if (_parse_date(e.get("event_at")) or start_at) >= start_at]
    if end_at:
        visible_events = [e for e in visible_events if (_parse_date(e.get("event_at")) or end_at) <= end_at]

    action = request.POST.get("action", "") if request.method == "POST" else ""
    mode = request.GET.get("mode", "reading")
    if mode not in {"reading", "replacement", "correction"}:
        mode = "reading"
    if action == "create_meter_event":
        mode = request.POST.get("event_type", "reading")
    form = MeterEventForm(request.POST if action == "create_meter_event" else None, initial={"asset_id": selected.get("id"), "event_type": mode} if selected else {"event_type": mode}, assets=assets, approved_readings=events)
    error_message = None
    if action == "create_meter_event":
        if not _can(identity, "equipment.meters.record"):
            return HttpResponse("ليس لديك صلاحية تسجيل حدث عداد", status=403)
        if form.is_valid():
            asset = next((a for a in assets if str(a["id"]) == str(form.cleaned_data["asset_id"])), None)
            if not asset:
                form.add_error("asset_id", "المعدة غير متاحة ضمن نطاقك.")
            else:
                try:
                    endpoint = {"reading": "meter-readings", "replacement": "meter-replacements", "correction": "meter-corrections"}[form.cleaned_data["event_type"]]
                    client.post(f"/equipment/assets/{asset['id']}/{endpoint}", form.payload())
                    return redirect(f"{request.path}?asset_id={asset['id']}&saved=1")
                except (UnauthorizedException, ForbiddenException, NotFoundException, ValidationException, ConflictException, ApiException) as exc:
                    error_message = str(exc)
    elif action == "approve_meter_event":
        if not _can(identity, "equipment.meters.approve"):
            return HttpResponse("ليس لديك صلاحية اعتماد القراءة", status=403)
        try:
            client.post(f"/equipment/meter-events/{request.POST.get('event_id')}/approve", {})
            return redirect(f"{request.path}?asset_id={selected_id}&approved=1")
        except (UnauthorizedException, ForbiddenException, NotFoundException, ValidationException, ConflictException, ApiException) as exc:
            error_message = str(exc)

    paginator = Paginator(assets, 8)
    page = paginator.get_page(request.GET.get("page", 1))
    for asset in all_assets:
        asset["meter_status_label"] = "معتمد" if asset.get("meter_latest") is not None else "لم تسجل قراءة"
        asset["meter_status_class"] = "approved" if asset.get("meter_latest") is not None else "empty"
    query = {k: v for k, v in {"search": search, "meter_type": meter_type, "location": location, "status": status_filter, "from": start_filter, "to": end_filter, "asset_id": selected_id}.items() if v}
    return render(request, "equipment/meters.html", {
        "identity": identity, "assets": page.object_list, "page_obj": page, "selected_asset": selected,
        "meter_events": visible_events[:20], "form": form, "form_mode": mode,
        "can_record": _can(identity, "equipment.meters.record"), "can_approve": _can(identity, "equipment.meters.approve"),
        "approved_count": sum(1 for a in all_assets if a.get("meter_latest") is not None),
        "pending_count": sum(1 for e in events if e.get("status") == "pending"),
        "review_count": sum(1 for e in events if e.get("status") == "pending" and e.get("event_type") in {"correction", "replacement"}),
        "replacement_count": sum(1 for e in events if e.get("event_type") == "replacement"),
        "meter_types": sorted({a.get("meter_type_locked") for a in all_assets if a.get("meter_type_locked")}),
        "locations": sorted({a.get("current_location") for a in all_assets if a.get("current_location")}),
        "query": urlencode(query) if query else "", "saved": request.GET.get("saved"), "approved": request.GET.get("approved"), "error_message": error_message,
    })
