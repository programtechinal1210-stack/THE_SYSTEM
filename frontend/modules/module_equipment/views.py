from uuid import UUID, uuid4
from urllib.parse import urlencode

from django.contrib import messages
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from shared.services.api_client import (
    ApiClient, ApiException, ConflictException, ForbiddenException, NotFoundException,
    UnauthorizedException, ValidationException,
)
from .forms import (
    AssetCreateForm,
    AssetForm,
    CategoryForm,
    EquipmentMovementForm,
    EquipmentRequestForm,
    InspectionForm,
    FuelEventForm,
    FuelInventoryMappingForm,
    MeterEventForm,
    PartInstallForm,
    PartRemovalForm,
    PartReplacementForm,
    MaintenanceCompletionForm,
    MaintenanceForm,
    MaintenancePlanForm,
    SafetyReleaseForm,
    EquipmentRequestPageForm,
    EquipmentAssignmentPageForm,
)


def _can(identity, permission):
    return identity.get("is_admin", False) or permission in identity.get("permissions", [])


def _asset_metadata_visible(asset, identity, field, permission):
    visibility = asset.get("metadata_visibility")
    if visibility is not None:
        return bool(visibility.get(field, False))
    return _can(identity, permission)


LIFECYCLE_LABELS = {
    "in_service": "ضمن الخدمة",
    "suspended": "موقوفة مؤقتاً",
    "retired": "متقاعدة",
    "disposed": "مستبعدة",
}
TECHNICAL_LABELS = {
    "unknown": "غير محددة",
    "unsafe": "غير آمنة",
    "maintenance": "تحت الصيانة",
    "out_of_service": "خارج الخدمة",
}
ASSIGNMENT_LABELS = {
    "approved": "مكلفة",
    "dispatched": "تم التوجيه",
    "active": "قيد التشغيل",
    "suspended": "التكليف موقوف",
}
BLOCKER_LABELS = {
    "CRITICAL_INSPECTION_FAILURE": "فشل فحص حرج",
    "MAINTENANCE_ORDER_OPEN": "يوجد أمر صيانة مفتوح",
}


@require_http_methods(["GET", "POST"])
def equipment_asset_create(request):
    client = ApiClient(token=request.session.get("access_token"))
    try:
        identity = client.get("/auth/me")
        modules = client.get("/modules")
    except UnauthorizedException:
        return redirect("auth:login")
    except ForbiddenException:
        return HttpResponse("ليس لديك صلاحية الوصول إلى إدارة المعدات", status=403)
    except NotFoundException:
        return HttpResponse("وحدة إدارة المعدات غير متاحة", status=404)
    except ApiException:
        return HttpResponse("تعذر تحميل إدارة المعدات؛ حاول مجددًا", status=503)

    if not (
        _can(identity, "equipment.assets.manage")
        and _can(identity, "equipment.categories.view")
    ):
        return HttpResponse("ليس لديك صلاحية إضافة المعدات ضمن نطاقك", status=403)

    organization_id = identity.get("organization_id")
    if not organization_id:
        return HttpResponse(
            "تعذر تحديد الجهة المؤسسية لحسابك؛ راجع مسؤول النظام قبل إضافة معدة",
            status=403,
        )
    try:
        options = client.get(
            "/equipment/asset-form-options", {"organization_id": organization_id}
        )
    except UnauthorizedException:
        return redirect("auth:login")
    except ForbiddenException:
        return HttpResponse("لا تتوفر صلاحية تحميل خيارات إضافة المعدات ضمن نطاقك", status=403)
    except NotFoundException:
        return HttpResponse("خيارات إضافة المعدات غير متاحة حالياً", status=404)
    except ValidationException:
        return HttpResponse("تعذر تحميل خيارات الإضافة للجهة المؤسسية المحددة", status=422)
    except ApiException:
        return HttpResponse("تعذر تحميل خيارات إضافة المعدات؛ حاول مجددًا", status=503)

    form = AssetCreateForm(
        request.POST if request.method == "POST" else None,
        categories=options.get("categories", []),
        organization_units=options.get("organization_units", []),
        currencies=options.get("currencies", []),
        responsible_entity_id=organization_id,
    )
    status_code = 200
    if request.method == "POST":
        form_valid = form.is_valid()
        action = request.POST.get("submit_action")
        if action not in {"save", "save_add_another"}:
            form.add_error(None, "اختر إجراء الحفظ المطلوب.")
            form_valid = False
        if form_valid:
            payload = form.payload()
            try:
                asset = client.post(
                    f"/equipment/assets?organization_id={organization_id}",
                    payload,
                )
            except UnauthorizedException:
                return redirect("auth:login")
            except ForbiddenException:
                return HttpResponse("ليس لديك صلاحية إضافة المعدة ضمن نطاقك", status=403)
            except NotFoundException:
                form.add_error(
                    "category_id",
                    "لم يعد التصنيف المحدد متاحاً. حدّث الصفحة واختر تصنيفاً نشطاً.",
                )
                status_code = 404
            except ConflictException:
                form.add_error(
                    "asset_code",
                    "رمز المعدة أو الرقم التسلسلي مستخدم مسبقاً ضمن الجهة.",
                )
                status_code = 409
            except ValidationException as exc:
                details = exc.args[0] if exc.args else None
                mapped_error = False
                if isinstance(details, list):
                    for error in details:
                        location = error.get("loc", ())
                        field_name = location[-1] if location else None
                        if field_name in form.fields:
                            form.add_error(
                                field_name,
                                "القيمة غير مقبولة. راجع بيانات هذا الحقل.",
                            )
                            mapped_error = True
                if not mapped_error:
                    form.add_error(
                        None, "لم يقبل النظام البيانات. راجع الحقول ثم أعد المحاولة."
                    )
                status_code = 422
            except ApiException:
                form.add_error(None, "تعذر حفظ المعدة الآن؛ احتفظ ببياناتك وأعد المحاولة.")
                status_code = 503
            else:
                messages.success(request, "تم حفظ المعدة بنجاح.")
                if action == "save_add_another":
                    return redirect("equipment:asset-create")
                if _can(identity, "equipment.assets.view"):
                    return redirect(
                        "equipment:asset-detail",
                        asset_id=UUID(str(asset["id"])),
                    )
                return redirect("equipment:home")
        else:
            status_code = 422

    for field_name in form.errors:
        if field_name in form.fields:
            form.fields[field_name].widget.attrs["aria-invalid"] = "true"

    return render(
        request,
        "equipment/asset_create.html",
        {
            "identity": identity,
            "core_modules": modules,
            "form": form,
            "has_categories": bool(options.get("categories")),
            "category_count": len(options.get("categories", [])),
            "currencies_count": len(options.get("currencies", [])),
            "meter_options": {
                str(item["id"]): {
                    "type": item["meter_type"],
                    "unit": item["meter_unit"],
                    "output_unit": item.get("output_unit") or "",
                }
                for item in options.get("categories", [])
            },
            "cancel_url": reverse("equipment:assets"),
        },
        status=status_code,
    )


def _decorate_asset(asset, identity):
    asset["detail_id"] = str(UUID(str(asset["id"])))
    asset["lifecycle_label"] = LIFECYCLE_LABELS.get(
        asset.get("lifecycle_status"), "غير معروفة"
    )
    asset["technical_label"] = TECHNICAL_LABELS.get(
        asset.get("technical_status"), "غير معروفة"
    )
    if _asset_metadata_visible(
        asset, identity, "assignments", "equipment.assignments.view"
    ):
        assignment_status = asset.get("assignment_status")
        asset["assignment_label"] = (
            ASSIGNMENT_LABELS.get(assignment_status, "غير مكلفة")
            if assignment_status
            else "غير مكلفة"
        )
    blockers = []
    if _asset_metadata_visible(
        asset, identity, "inspection_blockers", "equipment.inspections.view"
    ):
        blockers.extend(
            BLOCKER_LABELS.get(code, f"سبب فحص موثق ({code})")
            for code in (asset.get("inspection_blocker_reasons") or "").split(",")
            if code
        )
    if _asset_metadata_visible(
        asset, identity, "maintenance_blockers", "equipment.maintenance.view"
    ):
        blockers.extend(
            BLOCKER_LABELS.get(code, f"سبب صيانة موثق ({code})")
            for code in (asset.get("maintenance_blocker_reasons") or "").split(",")
            if code
        )
    asset["safety_blockers"] = blockers
    return asset


def _summary_count(*items):
    if any(len(result.get("items", [])) >= 200 for result in items):
        return "200+"
    return sum(len(result.get("items", [])) for result in items)


REQUEST_STATUS_LABELS = {
    "submitted": "بانتظار الاعتماد",
    "approved": "معتمد",
    "partially_fulfilled": "تلبية جزئية",
    "fulfilled": "مكتمل",
    "rejected": "مرفوض",
    "cancelled": "ملغى",
}
REQUEST_PRIORITY_LABELS = {
    "low": "منخفضة",
    "normal": "متوسطة",
    "high": "عالية",
    "critical": "حرجة",
}


def _decorate_equipment_request(item, categories, organization_units, fulfilled_by_request):
    item = dict(item)
    category = next(
        (row for row in categories if str(row.get("id")) == str(item.get("category_id"))),
        None,
    )
    entity = next(
        (row for row in organization_units if str(row.get("id")) == str(item.get("requested_entity_id"))),
        None,
    )
    item["category_name"] = (
        f'{category.get("category_code", "")} — {category.get("name_ar", "")}'.strip(" —")
        if category else "تصنيف غير متاح"
    )
    item["requested_entity_name"] = entity.get("name", "جهة غير متاحة") if entity else "جهة غير متاحة"
    item["status_label"] = REQUEST_STATUS_LABELS.get(item.get("status"), "غير محددة")
    item["priority_label"] = REQUEST_PRIORITY_LABELS.get(item.get("priority"), "غير محددة")
    item["fulfilled_quantity"] = fulfilled_by_request.get(str(item.get("id")), 0)
    item["remaining_quantity"] = max(
        0, int(item.get("required_quantity") or 0) - item["fulfilled_quantity"]
    )
    return item


@require_http_methods(["GET", "POST"])
def equipment_requests(request):
    """Focused EMO request workspace; distribution remains a separate workflow."""
    client = ApiClient(token=request.session.get("access_token"))
    try:
        identity = client.get("/auth/me")
        modules = client.get("/modules")
    except UnauthorizedException:
        return redirect("auth:login")
    except ForbiddenException:
        return HttpResponse("ليس لديك صلاحية الوصول إلى وحدة المعدات", status=403)
    except ApiException:
        return HttpResponse("تعذر الاتصال بخدمة المعدات؛ حاول مجددًا", status=503)

    can_view = _can(identity, "equipment.requests.view")
    can_create = _can(identity, "equipment.requests.create")
    can_approve = _can(identity, "equipment.requests.approve")
    can_reject = _can(identity, "equipment.requests.reject")
    if not can_view and not can_create:
        return HttpResponse("ليس لديك صلاحية عرض أو إنشاء طلبات المعدات", status=403)

    categories = {"items": []}
    organization_units = []
    if _can(identity, "equipment.categories.view"):
        try:
            categories = client.get("/equipment/categories", {"limit": 200})
        except ApiException:
            return HttpResponse("تعذر تحميل تصنيفات المعدات؛ حاول مجددًا", status=503)
    try:
        organization_units = client.get("/org-units")
    except (ForbiddenException, NotFoundException):
        if identity.get("organization_id"):
            organization_units = [{
                "id": identity["organization_id"],
                "name": identity.get("organization_name") or "الجهة الحالية",
                "is_active": True,
            }]
    except ApiException:
        organization_units = []

    raw_requests = {"items": []}
    if can_view:
        try:
            raw_requests = client.get("/equipment/requests")
        except UnauthorizedException:
            return redirect("auth:login")
        except ForbiddenException:
            return HttpResponse("ليس لديك صلاحية عرض طلبات المعدات", status=403)
        except ApiException:
            return HttpResponse("تعذر تحميل طلبات المعدات؛ حاول مجددًا", status=503)

    fulfilled_by_request = {}
    if _can(identity, "equipment.assignments.view"):
        try:
            assignments = client.get("/equipment/assignments").get("items", [])
            for assignment in assignments:
                if assignment.get("request_id") and assignment.get("status") in {
                    "approved", "dispatched", "active", "suspended", "completed",
                }:
                    key = str(assignment["request_id"])
                    fulfilled_by_request[key] = fulfilled_by_request.get(key, 0) + 1
        except ApiException:
            pass

    all_requests = [
        _decorate_equipment_request(
            item, categories.get("items", []), organization_units, fulfilled_by_request
        )
        for item in raw_requests.get("items", [])
    ]

    response_status = 200
    if request.method == "POST":
        action = request.POST.get("action", "")
        if action == "create_request":
            if not can_create or not _can(identity, "equipment.categories.view"):
                return HttpResponse("تتطلب إضافة الطلب صلاحية إنشاء الطلب وعرض التصنيفات", status=403)
            form = EquipmentRequestPageForm(
                request.POST,
                categories=categories.get("items", []),
                organization_units=organization_units,
            )
            if form.is_valid():
                try:
                    payload = form.payload()
                    client.post(
                        f"/equipment/requests?organization_id={identity.get('organization_id')}",
                        data=payload,
                    )
                except UnauthorizedException:
                    return redirect("auth:login")
                except ForbiddenException:
                    form.add_error(None, "لا تملك صلاحية إنشاء الطلب ضمن نطاقك الحالي.")
                    response_status = 403
                except (ValidationException, ConflictException) as exc:
                    form.add_error(None, str(exc))
                    response_status = 422
                except ApiException:
                    form.add_error(None, "تعذر حفظ الطلب؛ احتفظ بالبيانات وحاول مرة أخرى.")
                    response_status = 503
                else:
                    messages.success(request, "تم إنشاء طلب المعدات وإرساله للاعتماد.")
                    return redirect("equipment:requests")
        elif action in {"approve_request", "reject_request"}:
            permission = "equipment.requests.approve" if action == "approve_request" else "equipment.requests.reject"
            if not _can(identity, permission):
                return HttpResponse("ليس لديك صلاحية تنفيذ قرار الطلب", status=403)
            try:
                request_id = UUID(request.POST.get("request_id", ""))
            except (TypeError, ValueError):
                return HttpResponse("معرف الطلب غير صالح", status=400)
            reason = request.POST.get("decision_reason", "").strip()
            if action == "reject_request" and not reason:
                return HttpResponse("سبب الرفض مطلوب", status=422)
            try:
                client.post(
                    f"/equipment/requests/{request_id}/{'approve' if action == 'approve_request' else 'reject'}",
                    data={"decision_reason": reason},
                )
            except UnauthorizedException:
                return redirect("auth:login")
            except ForbiddenException:
                return HttpResponse("ليس لديك صلاحية تنفيذ قرار الطلب", status=403)
            except (NotFoundException, ValidationException, ConflictException) as exc:
                return HttpResponse(str(exc), status=409 if isinstance(exc, ConflictException) else 422)
            except ApiException:
                return HttpResponse("تعذر تحديث الطلب؛ حاول مجددًا", status=503)
            messages.success(request, "تم تحديث حالة الطلب.")
            return redirect(f"{reverse('equipment:requests')}?request_id={request_id}")
        else:
            return HttpResponse("إجراء طلب غير معروف", status=400)
    else:
        form = EquipmentRequestPageForm(
            categories=categories.get("items", []),
            organization_units=organization_units,
        )

    search = request.GET.get("search", "").strip().casefold()
    status_filter = request.GET.get("status", "").strip()
    entity_filter = request.GET.get("requested_entity_id", "").strip()
    category_filter = request.GET.get("category_id", "").strip()
    start_filter = request.GET.get("required_start", "").strip()
    end_filter = request.GET.get("required_end", "").strip()
    filtered = all_requests
    if search:
        filtered = [row for row in filtered if search in " ".join(
            str(row.get(key, "")) for key in (
                "request_code", "purpose", "target_location", "category_name", "requested_entity_name"
            )
        ).casefold()]
    if status_filter in REQUEST_STATUS_LABELS:
        filtered = [row for row in filtered if row.get("status") == status_filter]
    if entity_filter:
        filtered = [row for row in filtered if str(row.get("requested_entity_id")) == entity_filter]
    if category_filter:
        filtered = [row for row in filtered if str(row.get("category_id")) == category_filter]
    if start_filter:
        filtered = [row for row in filtered if str(row.get("required_start", ""))[:10] >= start_filter]
    if end_filter:
        filtered = [row for row in filtered if str(row.get("required_end", ""))[:10] <= end_filter]

    try:
        page = max(1, int(request.GET.get("page", "1")))
    except (TypeError, ValueError):
        page = 1
    page_size = 12
    page_count = max(1, (len(filtered) + page_size - 1) // page_size)
    page = min(page, page_count)
    visible_requests = filtered[(page - 1) * page_size:page * page_size]
    selected_id = request.GET.get("request_id", "").strip()
    selected_request = next((row for row in all_requests if str(row.get("id")) == selected_id), None)
    query = {
        key: value for key, value in {
            "search": search, "status": status_filter, "requested_entity_id": entity_filter,
            "category_id": category_filter, "required_start": start_filter, "required_end": end_filter,
        }.items() if value
    }

    def page_url(target):
        return f"{reverse('equipment:requests')}?{urlencode({**query, 'page': target})}"

    counts = {status: sum(row.get("status") == status for row in all_requests) for status in REQUEST_STATUS_LABELS}
    return render(request, "equipment/requests.html", {
        "identity": identity, "core_modules": modules, "request_form": form,
        "requests": visible_requests, "selected_request": selected_request,
        "total": len(filtered), "page": page, "page_count": page_count,
        "counts": counts, "status_labels": REQUEST_STATUS_LABELS,
        "categories": categories.get("items", []), "organization_units": organization_units,
        "active_filters": query, "previous_url": page_url(page - 1) if page > 1 else None,
        "next_url": page_url(page + 1) if page < page_count else None,
        "can_create_requests": can_create and _can(identity, "equipment.categories.view"),
        "can_approve_requests": can_approve, "can_reject_requests": can_reject,
        "create_mode": request.GET.get("create") == "1" or bool(form.errors),
    }, status=response_status)


ASSIGNMENT_STATUS_LABELS = {
    "draft": "مسودة",
    "approved": "معتمد",
    "dispatched": "تم التوجيه",
    "active": "نشط",
    "suspended": "معلق",
    "completed": "منتهٍ",
    "cancelled": "ملغى",
}


def _assignment_overlap(assignment, start, end):
    if not start or not end or assignment.get("status") not in {"approved", "dispatched", "active", "suspended"}:
        return False
    return str(assignment.get("planned_start_at", "")) < end and start < str(assignment.get("planned_end_at", ""))


@require_http_methods(["GET", "POST"])
def equipment_assignments(request):
    """Focused UI-06 workspace backed only by the existing EMO contracts."""
    client = ApiClient(token=request.session.get("access_token"))
    try:
        identity = client.get("/auth/me")
        modules = client.get("/modules")
    except UnauthorizedException:
        return redirect("auth:login")
    except ForbiddenException:
        return HttpResponse("لا تملك صلاحية الوصول إلى واجهة التكليفات", status=403)
    except ApiException:
        return HttpResponse("تعذر الاتصال بخدمة المعدات؛ حاول مجدداً", status=503)

    can_view = _can(identity, "equipment.assignments.view")
    can_create = _can(identity, "equipment.assignments.create")
    can_approve = _can(identity, "equipment.assignments.approve")
    if not can_view and not can_create:
        return HttpResponse("لا تملك صلاحية عرض أو إنشاء التكليفات", status=403)

    try:
        organization_units = client.get("/org-units")
    except (ForbiddenException, NotFoundException):
        organization_units = [{
            "id": identity.get("organization_id"),
            "name": identity.get("organization_name") or "الجهة الحالية",
            "is_active": True,
        }] if identity.get("organization_id") else []
    except ApiException:
        organization_units = []

    assets_result = {"items": []}
    categories_result = {"items": []}
    assignments_result = {"items": []}
    requests_result = {"items": []}
    employees_result = {"items": []}
    def optional_get(endpoint, params=None, default=None):
        try:
            return client.get(endpoint, params) if params else client.get(endpoint)
        except UnauthorizedException:
            raise
        except ApiException:
            return default if default is not None else {}

    try:
        if _can(identity, "equipment.assets.view"):
            assets_result = optional_get("/equipment/assets", {"limit": 200, "sort_by": "asset_code", "sort_dir": "asc"}, assets_result)
        if _can(identity, "equipment.categories.view"):
            categories_result = optional_get("/equipment/categories", {"limit": 200}, categories_result)
        if can_view:
            assignments_result = optional_get("/equipment/assignments", default=assignments_result)
        if _can(identity, "equipment.requests.view"):
            requests_result = optional_get("/equipment/requests", default=requests_result)
        if _can(identity, "hr.employees.view"):
            employees_result = optional_get("/hr/employees", {"employment_status": "active", "page_size": 100}, employees_result)
    except UnauthorizedException:
        return redirect("auth:login")

    if isinstance(organization_units, dict):
        organization_units = organization_units.get("items", [])
    raw_assets = assets_result.get("items", [])
    assignments = assignments_result.get("items", [])
    categories = categories_result.get("items", [])
    organization_units = [row for row in organization_units if row.get("is_active", True)]
    employees = employees_result.get("items", [])
    approved_requests = [row for row in requests_result.get("items", []) if row.get("status") in {"approved", "partially_fulfilled"}]

    start_filter = request.GET.get("planned_start_at", "").strip()
    end_filter = request.GET.get("planned_end_at", "").strip()
    period_start = start_filter.replace(" ", "T") if start_filter else None
    period_end = end_filter.replace(" ", "T") if end_filter else None
    category_names = {str(row.get("id")): row.get("name_ar") or row.get("category_name") or row.get("category_code") for row in categories}
    asset_by_id = {str(row.get("id")): row for row in raw_assets}
    for asset in raw_assets:
        asset["category_display"] = category_names.get(str(asset.get("category_id")), asset.get("category_name", "تصنيف غير محدد"))
        asset["availability_reason"] = "متاحة للاختيار"
        asset["available_for_period"] = True
        if asset.get("lifecycle_status") != "in_service":
            asset["available_for_period"] = False
            asset["availability_reason"] = "الحالة الحياتية لا تسمح بالتكليف"
        elif asset.get("technical_status") in {"unsafe", "maintenance", "out_of_service"}:
            asset["available_for_period"] = False
            asset["availability_reason"] = {"unsafe": "عليها مانع سلامة", "maintenance": "تحت الصيانة", "out_of_service": "خارج الخدمة"}.get(asset.get("technical_status"), "غير متاحة")
        elif period_start and period_end:
            conflict = next((row for row in assignments if str(row.get("asset_id")) == str(asset.get("id")) and _assignment_overlap(row, period_start, period_end)), None)
            if conflict:
                asset["available_for_period"] = False
                asset["availability_reason"] = "محجوزة خلال الفترة المحددة"
            elif asset.get("inspection_blocker_reasons") or asset.get("maintenance_blocker_reasons"):
                asset["available_for_period"] = False
                asset["availability_reason"] = "توجد موانع فحص أو صيانة نشطة"

    decorated_assignments = []
    for item in assignments:
        row = dict(item)
        asset = asset_by_id.get(str(row.get("asset_id")), {})
        entity = next((x for x in organization_units if str(x.get("id")) == str(row.get("beneficiary_entity_id"))), None)
        row["asset_name"] = row.get("asset_name") or asset.get("asset_name", "معدة غير متاحة")
        row["asset_code"] = row.get("asset_code") or asset.get("asset_code", "—")
        row["beneficiary_name"] = entity.get("name") if entity else "الجهة المستفيدة غير متاحة"
        row["status_label"] = ASSIGNMENT_STATUS_LABELS.get(row.get("status"), "غير محدد")
        decorated_assignments.append(row)

    form_kwargs = {
        "assets": raw_assets,
        "organization_units": organization_units,
        "employees": employees,
        "requests": approved_requests,
    }
    response_status = 200
    if request.method == "POST":
        action = request.POST.get("action", "")
        if action == "create_assignment":
            if not can_create:
                return HttpResponse("لا تملك صلاحية إنشاء التكليف", status=403)
            form = EquipmentAssignmentPageForm(request.POST, **form_kwargs)
            if form.is_valid():
                payload = form.payload()
                payload["idempotency_key"] = uuid4().hex
                try:
                    created = client.post("/equipment/assignments", data=payload)
                except UnauthorizedException:
                    return redirect("auth:login")
                except (ValidationException, ConflictException) as exc:
                    form.add_error(None, str(exc))
                    response_status = 409 if isinstance(exc, ConflictException) else 422
                except ForbiddenException:
                    form.add_error(None, "لا تملك صلاحية إنشاء هذا التكليف ضمن نطاقك.")
                    response_status = 403
                except ApiException:
                    form.add_error(None, "تعذر حفظ التكليف؛ احتفظ بالبيانات وحاول مجدداً.")
                    response_status = 503
                else:
                    messages.success(request, "تم حفظ التكليف كمسودة. الاعتماد مطلوب قبل التشغيل.")
                    return redirect(f"{reverse('equipment:assignments')}?assignment_id={created.get('id')}")
        elif action == "approve_assignment":
            if not can_approve:
                return HttpResponse("لا تملك صلاحية اعتماد التكليف", status=403)
            assignment_id = request.POST.get("assignment_id", "")
            try:
                assignment_uuid = UUID(assignment_id)
            except (TypeError, ValueError):
                return HttpResponse("معرف التكليف غير صالح", status=400)
            try:
                client.post(f"/equipment/assignments/{assignment_uuid}/approve")
            except UnauthorizedException:
                return redirect("auth:login")
            except ConflictException as exc:
                return HttpResponse(str(exc), status=409)
            except (ForbiddenException, NotFoundException, ValidationException) as exc:
                return HttpResponse(str(exc), status=403 if isinstance(exc, ForbiddenException) else 422)
            except ApiException:
                return HttpResponse("تعذر اعتماد التكليف؛ حاول مجدداً", status=503)
            messages.success(request, "تم اعتماد التكليف بعد إعادة فحص التعارض والجاهزية.")
            return redirect(f"{reverse('equipment:assignments')}?assignment_id={assignment_id}")
        else:
            return HttpResponse("إجراء تكليف غير معروف", status=400)
    else:
        initial = {}
        request_ref = request.GET.get("request_id", "").strip()
        linked = next((row for row in approved_requests if str(row.get("id")) == request_ref), None)
        if linked:
            initial = {
                "beneficiary_entity_id": linked.get("requested_entity_id"),
                "planned_start_at": str(linked.get("required_start", ""))[:16].replace("Z", ""),
                "planned_end_at": str(linked.get("required_end", ""))[:16].replace("Z", ""),
                "purpose": linked.get("purpose", ""),
                "request_id": linked.get("id"),
            }
        form = EquipmentAssignmentPageForm(initial=initial, **form_kwargs)

    search = request.GET.get("search", "").strip().casefold()
    status_filter = request.GET.get("status", "").strip()
    entity_filter = request.GET.get("beneficiary_entity_id", "").strip()
    filtered = decorated_assignments
    if search:
        filtered = [row for row in filtered if search in " ".join(str(row.get(key, "")) for key in ("asset_code", "asset_name", "beneficiary_name", "purpose")).casefold()]
    if status_filter in ASSIGNMENT_STATUS_LABELS:
        filtered = [row for row in filtered if row.get("status") == status_filter]
    if entity_filter:
        filtered = [row for row in filtered if str(row.get("beneficiary_entity_id")) == entity_filter]
    selected_id = request.GET.get("assignment_id", "").strip()
    selected_assignment = next((row for row in decorated_assignments if str(row.get("id")) == selected_id), None)
    selected_asset = asset_by_id.get(str(selected_assignment.get("asset_id"))) if selected_assignment else None
    page_size = 12
    try:
        page = max(1, int(request.GET.get("page", "1")))
    except (TypeError, ValueError):
        page = 1
    page_count = max(1, (len(filtered) + page_size - 1) // page_size)
    page = min(page, page_count)
    visible_assignments = filtered[(page - 1) * page_size:page * page_size]
    return render(request, "equipment/assignments.html", {
        "identity": identity, "core_modules": modules, "assignments": visible_assignments,
        "all_assignments": decorated_assignments, "selected_assignment": selected_assignment,
        "selected_asset": selected_asset, "assignment_form": form, "assets": raw_assets,
        "available_assets": [row for row in raw_assets if row.get("available_for_period")],
        "organization_units": organization_units, "requests": approved_requests,
        "total": len(filtered), "page": page, "page_count": page_count,
        "counts": {status: sum(row.get("status") == status for row in decorated_assignments) for status in ASSIGNMENT_STATUS_LABELS},
        "status_labels": ASSIGNMENT_STATUS_LABELS, "active_filters": request.GET,
        "can_create_assignments": can_create, "can_approve_assignments": can_approve,
        "create_mode": request.GET.get("create") == "1" or bool(form.errors),
        "previous_url": None, "next_url": None,
    }, status=response_status)


MOVEMENT_STATUS_LABELS = {
    "draft": "مسودة — بانتظار التسليم",
    "dispatched": "تم التسليم — بانتظار الاستلام",
    "received": "تم الاستلام",
    "cancelled": "ملغاة",
}


@require_http_methods(["GET", "POST"])
def equipment_movements(request):
    """Focused UI-07 workspace using the existing movement lifecycle contracts."""
    client = ApiClient(token=request.session.get("access_token"))
    try:
        identity = client.get("/auth/me")
        modules = client.get("/modules")
    except UnauthorizedException:
        return redirect("auth:login")
    except ForbiddenException:
        return HttpResponse("لا تملك صلاحية الوصول إلى حركات المعدات", status=403)
    except ApiException:
        return HttpResponse("تعذر الاتصال بخدمة المعدات؛ حاول مجدداً", status=503)

    can_view = _can(identity, "equipment.movements.view")
    can_create = _can(identity, "equipment.movements.create")
    can_dispatch = _can(identity, "equipment.movements.dispatch")
    can_receive = _can(identity, "equipment.movements.receive")
    can_cancel = _can(identity, "equipment.movements.cancel")
    if not can_view:
        return HttpResponse("لا تملك صلاحية عرض حركات المعدات", status=403)

    def get_optional(endpoint, params=None, default=None):
        try:
            return client.get(endpoint, params) if params else client.get(endpoint)
        except UnauthorizedException:
            raise
        except ApiException:
            return default if default is not None else {}

    try:
        assets_result = get_optional(
            "/equipment/assets",
            {"limit": 200, "sort_by": "asset_code", "sort_dir": "asc"},
            {"items": []},
        )
        movements_result = client.get("/equipment/movements")
    except UnauthorizedException:
        return redirect("auth:login")
    except ForbiddenException:
        return HttpResponse("لا تملك صلاحية عرض حركات المعدات", status=403)
    except (NotFoundException, ApiException):
        return HttpResponse("تعذر تحميل حركات المعدات؛ حاول مجدداً", status=503)

    raw_assets = assets_result.get("items", [])
    asset_by_id = {str(row.get("id")): row for row in raw_assets}
    movements = []
    for raw in movements_result.get("items", []):
        row = dict(raw)
        asset = asset_by_id.get(str(row.get("asset_id")), {})
        row["asset_name"] = row.get("asset_name") or asset.get("asset_name") or "معدة غير متاحة"
        row["asset_code"] = row.get("asset_code") or asset.get("asset_code") or "—"
        row["asset_location"] = asset.get("current_location") or "غير محدد"
        row["status_label"] = MOVEMENT_STATUS_LABELS.get(row.get("status"), "غير محددة")
        row["registered_at"] = row.get("created_at") or row.get("movement_date") or ""
        movements.append(row)

    form = EquipmentMovementForm(request.POST or None, assets=raw_assets)
    response_status = 200
    selected_id = request.GET.get("movement_id", "").strip()
    if request.method == "POST":
        action = request.POST.get("action", "")
        if action == "create_movement":
            if not can_create:
                return HttpResponse("لا تملك صلاحية تسجيل حركة", status=403)
            form = EquipmentMovementForm(request.POST, assets=raw_assets)
            if form.is_valid():
                payload = form.payload()
                payload["idempotency_key"] = uuid4().hex
                try:
                    created = client.post("/equipment/movements", data=payload)
                except UnauthorizedException:
                    return redirect("auth:login")
                except ForbiddenException:
                    form.add_error(None, "لا تملك صلاحية تسجيل حركة ضمن نطاقك المؤسسي.")
                    response_status = 403
                except (ValidationException, ConflictException) as exc:
                    form.add_error(None, str(exc))
                    response_status = 409 if isinstance(exc, ConflictException) else 422
                except ApiException:
                    form.add_error(None, "تعذر حفظ الحركة؛ احتفظ بالبيانات وحاول مجدداً.")
                    response_status = 503
                else:
                    messages.success(request, "تم تسجيل الحركة كمسودة. يلزم التسليم قبل الاستلام.")
                    return redirect(f"{reverse('equipment:movements')}?movement_id={created.get('id')}")
        elif action in {"dispatch_movement", "receive_movement", "cancel_movement"}:
            permission = {
                "dispatch_movement": can_dispatch,
                "receive_movement": can_receive,
                "cancel_movement": can_cancel,
            }[action]
            if not permission:
                return HttpResponse("لا تملك صلاحية تنفيذ هذا الإجراء", status=403)
            try:
                movement_id = UUID(request.POST.get("movement_id", ""))
            except (TypeError, ValueError):
                return HttpResponse("معرف الحركة غير صالح", status=400)
            endpoint_action = {
                "dispatch_movement": "dispatch",
                "receive_movement": "receive",
                "cancel_movement": "cancel",
            }[action]
            data = {}
            if action == "receive_movement":
                condition = request.POST.get("condition_at_receipt", "").strip()
                if not condition:
                    return HttpResponse("حالة المعدة عند الاستلام مطلوبة", status=422)
                data["condition_at_receipt"] = condition
            try:
                client.post(f"/equipment/movements/{movement_id}/{endpoint_action}", data=data)
            except UnauthorizedException:
                return redirect("auth:login")
            except ForbiddenException as exc:
                return HttpResponse(str(exc), status=403)
            except NotFoundException as exc:
                return HttpResponse(str(exc), status=404)
            except ValidationException as exc:
                return HttpResponse(str(exc), status=422)
            except ConflictException as exc:
                return HttpResponse(str(exc), status=409)
            except ApiException:
                return HttpResponse("تعذر تحديث الحركة؛ حاول مجدداً", status=503)
            messages.success(request, "تم تحديث حركة المعدة.")
            return redirect(f"{reverse('equipment:movements')}?movement_id={movement_id}")
        else:
            return HttpResponse("إجراء حركة غير معروف", status=400)

    search = request.GET.get("search", "").strip().casefold()
    status_filter = request.GET.get("status", "").strip()
    from_filter = request.GET.get("from_location", "").strip().casefold()
    to_filter = request.GET.get("to_location", "").strip().casefold()
    filtered = movements
    if search:
        filtered = [row for row in filtered if search in " ".join(
            str(row.get(key, "")) for key in ("movement_code", "asset_code", "asset_name", "from_location", "to_location")
        ).casefold()]
    if status_filter in MOVEMENT_STATUS_LABELS:
        filtered = [row for row in filtered if row.get("status") == status_filter]
    if from_filter:
        filtered = [row for row in filtered if from_filter in str(row.get("from_location", "")).casefold()]
    if to_filter:
        filtered = [row for row in filtered if to_filter in str(row.get("to_location", "")).casefold()]
    selected = next((row for row in movements if str(row.get("id")) == selected_id), None)
    page_size = 12
    try:
        page = max(1, int(request.GET.get("page", "1")))
    except (TypeError, ValueError):
        page = 1
    page_count = max(1, (len(filtered) + page_size - 1) // page_size)
    page = min(page, page_count)
    visible = filtered[(page - 1) * page_size:page * page_size]
    return render(request, "equipment/movements.html", {
        "identity": identity, "core_modules": modules, "movements": visible,
        "all_movements": movements, "selected_movement": selected, "assets": raw_assets,
        "movement_form": form, "total": len(filtered), "page": page, "page_count": page_count,
        "counts": {status: sum(row.get("status") == status for row in movements) for status in MOVEMENT_STATUS_LABELS},
        "status_labels": MOVEMENT_STATUS_LABELS, "can_create_movements": can_create,
        "can_dispatch_movements": can_dispatch, "can_receive_movements": can_receive,
        "can_cancel_movements": can_cancel, "create_mode": request.GET.get("create") == "1" or bool(form.errors),
        "active_filters": request.GET,
    }, status=response_status)


@require_http_methods(["GET"])
def equipment_assets(request):
    client = ApiClient(token=request.session.get("access_token"))
    try:
        identity = client.get("/auth/me")
        modules = client.get("/modules")
    except UnauthorizedException:
        return redirect("auth:login")
    except ForbiddenException:
        return HttpResponse("ليس لديك صلاحية الوصول إلى إدارة المعدات", status=403)
    except NotFoundException:
        return HttpResponse("وحدة إدارة المعدات غير متاحة", status=404)
    except ApiException:
        return HttpResponse("تعذر تحميل إدارة المعدات؛ حاول مجددًا", status=503)

    if not _can(identity, "equipment.assets.view"):
        return HttpResponse("ليس لديك صلاحية عرض سجل المعدات", status=403)

    def optional_uuid(name):
        value = request.GET.get(name, "").strip()
        if not value:
            return None
        try:
            return str(UUID(value))
        except (TypeError, ValueError):
            raise ValueError(name) from None

    lifecycle_status = request.GET.get("lifecycle_status", "").strip()
    technical_status = request.GET.get("technical_status", "").strip()
    sort_by = request.GET.get("sort_by", "asset_code").strip()
    sort_dir = request.GET.get("sort_dir", "asc").strip()
    if lifecycle_status and lifecycle_status not in LIFECYCLE_LABELS:
        return HttpResponse("قيمة حالة المعدة غير صالحة", status=400)
    if technical_status and technical_status not in TECHNICAL_LABELS:
        return HttpResponse("قيمة الحالة الفنية غير صالحة", status=400)
    if sort_by not in {
        "asset_code", "asset_name", "category_name", "lifecycle_status",
        "current_location", "created_at",
    } or sort_dir not in {"asc", "desc"}:
        return HttpResponse("خيار الترتيب غير صالح", status=400)
    try:
        category_id = optional_uuid("category_id")
        responsible_entity_id = optional_uuid("responsible_entity_id")
    except ValueError:
        return HttpResponse("معرّف التصفية غير صالح", status=400)

    try:
        page = int(request.GET.get("page", "1"))
    except (TypeError, ValueError):
        return HttpResponse("رقم الصفحة غير صالح", status=400)
    if page < 1:
        return HttpResponse("رقم الصفحة غير صالح", status=400)
    page_size = 24
    active_filters = {
        key: value for key, value in {
            "search": request.GET.get("search", "").strip(),
            "category_id": category_id,
            "lifecycle_status": lifecycle_status,
            "technical_status": technical_status,
            "responsible_entity_id": responsible_entity_id,
            "location": request.GET.get("location", "").strip(),
        }.items() if value
    }
    api_params = {
        "skip": (page - 1) * page_size,
        "limit": page_size,
        "sort_by": sort_by,
        "sort_dir": sort_dir,
        **active_filters,
    }
    try:
        result = client.get("/equipment/assets", api_params)
    except UnauthorizedException:
        return redirect("auth:login")
    except ForbiddenException:
        return HttpResponse("ليس لديك صلاحية عرض سجل المعدات ضمن نطاقك", status=403)
    except NotFoundException:
        return HttpResponse("وحدة إدارة المعدات غير متاحة", status=404)
    except ApiException:
        return HttpResponse("تعذر تحميل سجل المعدات؛ حاول مجددًا", status=503)

    total = result.get("total", len(result.get("items", [])))
    page_count = max(1, (total + page_size - 1) // page_size)
    if page > page_count:
        query = {**active_filters, "sort_by": sort_by, "sort_dir": sort_dir,
                 "page": page_count}
        return HttpResponseRedirect(f"{reverse('equipment:assets')}?{urlencode(query)}")

    assets = [_decorate_asset(asset, identity) for asset in result.get("items", [])]
    filter_options = result.get("filter_options", {})
    for option in filter_options.get("categories", []):
        option["selected"] = str(option["id"]).replace("-", "").lower() == (
            category_id or ""
        ).replace("-", "").lower()
    for option in filter_options.get("responsible_entities", []):
        option["selected"] = str(option["id"]).replace("-", "").lower() == (
            responsible_entity_id or ""
        ).replace("-", "").lower()
    page_query = {**active_filters, "sort_by": sort_by, "sort_dir": sort_dir}

    def page_url(target_page):
        return f"{reverse('equipment:assets')}?{urlencode({**page_query, 'page': target_page, 'view': request.GET.get('view', 'cards')})}"

    context = {
        "identity": identity,
        "core_modules": modules,
        "assets": assets,
        "total": total,
        "page": page,
        "page_count": page_count,
        "first_result": (page - 1) * page_size + 1 if total else 0,
        "last_result": min(page * page_size, total),
        "categories": filter_options.get("categories", []),
        "responsible_entities": filter_options.get("responsible_entities", []),
        "locations": filter_options.get("locations", []),
        "active_filters": active_filters,
        "sort_by": sort_by,
        "sort_dir": sort_dir,
        "view_mode": request.GET.get("view", "cards")
        if request.GET.get("view") in {"cards", "table"} else "cards",
        "can_view_assignments": result.get("metadata_visibility", {}).get(
            "assignments", _can(identity, "equipment.assignments.view")
        ),
        "previous_url": page_url(page - 1) if page > 1 else None,
        "next_url": page_url(page + 1) if page < page_count else None,
        "can_add_asset": (
            _can(identity, "equipment.assets.manage")
            and _can(identity, "equipment.categories.view")
        ),
        "add_asset_url": reverse("equipment:asset-create"),
    }
    return render(request, "equipment/assets.html", context)


@require_http_methods(["GET"])
def equipment_asset_detail(request, asset_id):
    client = ApiClient(token=request.session.get("access_token"))
    try:
        identity = client.get("/auth/me")
        modules = client.get("/modules")
    except UnauthorizedException:
        return redirect("auth:login")
    except ForbiddenException:
        return HttpResponse("ليس لديك صلاحية الوصول إلى إدارة المعدات", status=403)
    except NotFoundException:
        return HttpResponse("وحدة إدارة المعدات غير متاحة", status=404)
    except ApiException:
        return HttpResponse("تعذر تحميل إدارة المعدات؛ حاول مجددًا", status=503)
    if not _can(identity, "equipment.assets.view"):
        return HttpResponse("ليس لديك صلاحية عرض سجل المعدات", status=403)

    try:
        asset = client.get(f"/equipment/assets/{asset_id}")
    except UnauthorizedException:
        return redirect("auth:login")
    except ForbiddenException:
        return HttpResponse("ليس لديك صلاحية عرض هذه المعدة ضمن نطاقك", status=403)
    except NotFoundException:
        return HttpResponse("المعدة غير متاحة ضمن النطاق المعروض", status=404)
    except ApiException:
        return HttpResponse("تعذر تحميل بطاقة المعدة؛ حاول مجددًا", status=503)

    asset = _decorate_asset(asset, identity)
    tab = request.GET.get("tab", "summary").strip().lower()
    tabs = {"summary", "assignments", "operations", "fuel", "maintenance", "parts", "movements", "costs", "documents"}
    if tab not in tabs:
        tab = "summary"

    # The detail page is an adapter: each tab reads only its existing EMO contract
    # when selected. No detail-page cache or duplicate source is created here.
    tab_data = {"items": []}
    tab_error = None
    readiness = None
    if tab == "summary":
        try:
            readiness = client.get(f"/equipment/assets/{asset_id}/readiness")
        except ApiException:
            tab_error = "تعذر التحقق من الجاهزية حالياً. لم يتم استنتاج حالة تشغيلية بديلة."
    else:
        endpoints = {
            "assignments": ("/equipment/assets/{}/assignments", "equipment.assignments.view"),
            "operations": ("/equipment/operations", "equipment.operations.view"),
            "fuel": ("/equipment/assets/{}/fuel-events", "equipment.fuel.view"),
            "maintenance": ("/equipment/maintenance-orders", "equipment.maintenance.view"),
            "parts": ("/equipment/assets/{}/part-lifecycles", "equipment.parts.view"),
            "movements": ("/equipment/assets/{}/movements", "equipment.movements.view"),
        }
        if tab in {"costs", "documents"}:
            tab_error = "هذا القسم غير متاح في عقد المعدات الحالي."
        elif not _can(identity, endpoints[tab][1]):
            tab_error = "لا تملك صلاحية عرض هذا القسم ضمن نطاقك الحالي."
        else:
            try:
                path = endpoints[tab][0].format(asset_id)
                params = {"asset_id": str(asset_id)} if tab in {"operations", "maintenance"} else None
                tab_data = client.get(path, params) if params else client.get(path)
                if tab == "fuel":
                    tab_data["balance"] = client.get(f"/equipment/assets/{asset_id}/fuel-balance").get("items", [])
            except (ForbiddenException, NotFoundException):
                tab_error = "البيانات غير متاحة ضمن نطاق الحساب الحالي."
            except ApiException:
                tab_error = "تعذر تحميل هذا القسم حالياً. حاول مرة أخرى."

    visibility = asset.get("metadata_visibility", {})
    can_view_assignments = visibility.get("assignments", _can(identity, "equipment.assignments.view"))
    can_view_blockers = (
        visibility.get("inspection_blockers", _can(identity, "equipment.inspections.view"))
        or visibility.get("maintenance_blockers", _can(identity, "equipment.maintenance.view"))
    )
    can_confirm_no_blockers = (
        visibility.get("inspection_blockers", _can(identity, "equipment.inspections.view"))
        and visibility.get("maintenance_blockers", _can(identity, "equipment.maintenance.view"))
    )
    context = {
        "identity": identity,
        "core_modules": modules,
        "asset": asset,
        "tab": tab,
        "tabs": tabs,
        "tab_data": tab_data,
        "tab_error": tab_error,
        "readiness": readiness,
        "can_view_assignments": can_view_assignments,
        "can_view_blockers": can_view_blockers,
        "can_confirm_no_blockers": can_confirm_no_blockers,
        "can_start_operation": _can(identity, "equipment.operations.start"),
        "can_record_inspection": _can(identity, "equipment.inspections.record"),
        "can_create_maintenance": _can(identity, "equipment.maintenance.create"),
        "can_record_fuel": _can(identity, "equipment.fuel.record"),
        "can_install_parts": (
            _can(identity, "equipment.parts.install")
            and _can(identity, "equipment.inventory.view")
            and _can(identity, "inventory.documents.view")
        ),
        "can_view_operations": _can(identity, "equipment.operations.view"),
        "can_view_fuel": _can(identity, "equipment.fuel.view"),
        "can_view_maintenance": _can(identity, "equipment.maintenance.view"),
        "can_view_parts": _can(identity, "equipment.parts.view"),
        "can_view_movements": _can(identity, "equipment.movements.view"),
    }
    return render(request, "equipment/asset_detail.html", context)


def _equipment_control_center(request, client, identity, modules, dashboard, can_view_assets):
    can_view_requests = _can(identity, "equipment.requests.view")
    can_view_maintenance = _can(identity, "equipment.maintenance.view")
    pending_requests = None
    active_maintenance = None
    can_create_movement = (
        _can(identity, "equipment.movements.create")
        and can_view_assets
        and dashboard.get("assets", {}).get("total", 0) > 0
    )

    try:
        if can_view_requests:
            pending_requests = client.get("/equipment/requests", {"status": "submitted"})
        if can_view_maintenance:
            open_orders = client.get("/equipment/maintenance-orders", {"status": "open"})
            in_progress_orders = client.get(
                "/equipment/maintenance-orders", {"status": "in_progress"}
            )
            active_maintenance = _summary_count(open_orders, in_progress_orders)
    except UnauthorizedException:
        return redirect("auth:login")
    except ForbiddenException:
        return HttpResponse("ليس لديك صلاحية عرض مؤشرات المعدات ضمن نطاقك", status=403)
    except NotFoundException:
        return HttpResponse("وحدة إدارة المعدات غير متاحة", status=404)
    except ApiException:
        return HttpResponse("تعذر تحميل مؤشرات المعدات؛ حاول مجددًا", status=503)

    context = {
        "identity": identity,
        "core_modules": modules,
        "dashboard": dashboard,
        "can_view_assets": can_view_assets,
        "can_view_requests": can_view_requests,
        "can_view_maintenance": can_view_maintenance,
        "pending_requests_count": (
            _summary_count(pending_requests) if pending_requests is not None else None
        ),
        "active_maintenance_count": active_maintenance,
        "can_open_registry": can_view_assets,
        "can_open_requests": (
            can_view_requests
            or (
                _can(identity, "equipment.requests.create")
                and _can(identity, "equipment.categories.view")
            )
            or _can(identity, "equipment.movements.view")
            or can_create_movement
        ),
        "can_open_assignments": (
            _can(identity, "equipment.assignments.view")
            or _can(identity, "equipment.assignments.create")
        ),
        "can_open_movements": _can(identity, "equipment.movements.view"),
        "can_open_operations": (
            _can(identity, "equipment.operations.view")
            or _can(identity, "equipment.operations.start")
        ),
        "can_open_inspections": (
            _can(identity, "equipment.inspections.view")
            or can_view_maintenance
        ),
        "can_open_fuel_meters": (
            _can(identity, "equipment.meters.view")
            or _can(identity, "equipment.fuel.view")
            or (
                can_view_assets
                and (
                    _can(identity, "equipment.meters.record")
                    or _can(identity, "equipment.fuel.record")
                )
            )
            or _can(identity, "equipment.inventory.view")
            or _can(identity, "equipment.inventory.manage")
        ),
        "can_open_parts": (
            can_view_assets
            and (
                _can(identity, "equipment.parts.view")
                or (
                    _can(identity, "equipment.parts.install")
                    and _can(identity, "equipment.inventory.view")
                    and _can(identity, "inventory.documents.view")
                )
            )
        ),
        "can_open_reports": (
            _can(identity, "equipment.reports.view")
            and bool(identity.get("organization_id"))
        ),
        "can_create_movement": can_create_movement,
        "can_add_asset": (
            _can(identity, "equipment.assets.manage")
            and _can(identity, "equipment.categories.view")
        ),
        "can_create_request": (
            _can(identity, "equipment.requests.create")
            and _can(identity, "equipment.categories.view")
        ),
        "can_start_operation": _can(identity, "equipment.operations.start"),
        "can_report_fault": (
            _can(identity, "equipment.maintenance.create")
            and can_view_assets
            and (
                _can(identity, "equipment.inspections.view")
                or can_view_maintenance
            )
        ),
    }
    return render(request, "equipment/control_center.html", context)


@require_http_methods(["GET", "POST"])
def equipment_home(request):
    client = ApiClient(token=request.session.get("access_token"))
    try:
        identity = client.get("/auth/me")
        modules = client.get("/modules")
    except UnauthorizedException:
        return redirect("auth:login")
    except ForbiddenException:
        return HttpResponse("ليس لديك صلاحية الوصول إلى إدارة المعدات", status=403)
    except NotFoundException:
        return HttpResponse("وحدة إدارة المعدات غير متاحة", status=404)
    except ApiException:
        return HttpResponse("تعذر تحميل إدارة المعدات؛ حاول مجددًا", status=503)

    can_view_assets = _can(identity, "equipment.assets.view")
    if can_view_assets:
        try:
            dashboard = client.get("/equipment/dashboard")
        except UnauthorizedException:
            return redirect("auth:login")
        except ForbiddenException:
            return HttpResponse("ليس لديك صلاحية عرض لوحة المعدات", status=403)
        except NotFoundException:
            return HttpResponse("وحدة إدارة المعدات غير متاحة", status=404)
        except ApiException:
            return HttpResponse("تعذر تحميل لوحة المعدات؛ حاول مجددًا", status=503)
    else:
        dashboard = {"assets": {"total": 0, "in_service": 0}, "readiness": "not_evaluated"}

    if (
        request.method == "GET"
        and request.GET.get("workspace") != "1"
        and not (request.GET.get("asset_id") or request.GET.get("search"))
    ):
        return _equipment_control_center(
            request, client, identity, modules, dashboard, can_view_assets
        )

    can_view_categories = _can(identity, "equipment.categories.view")
    try:
        categories = client.get("/equipment/categories", {"limit": 50}) if can_view_categories else {"items": []}
    except UnauthorizedException:
        return redirect("auth:login")
    except ForbiddenException:
        return HttpResponse("ليس لديك صلاحية عرض تصنيفات المعدات", status=403)
    except NotFoundException:
        return HttpResponse("وحدة إدارة المعدات غير متاحة", status=404)
    except ApiException:
        return HttpResponse("تعذر تحميل تصنيفات المعدات؛ حاول مجددًا", status=503)

    if can_view_assets:
        try:
            assets = client.get("/equipment/assets", {
                "search": request.GET.get("search", ""),
                "limit": 100,
            })
        except UnauthorizedException:
            return redirect("auth:login")
        except ForbiddenException:
            return HttpResponse("ليس لديك صلاحية عرض سجل المعدات", status=403)
        except NotFoundException:
            return HttpResponse("وحدة إدارة المعدات غير متاحة", status=404)
        except ApiException:
            return HttpResponse("تعذر تحميل سجل المعدات؛ حاول مجددًا", status=503)
    else:
        assets = {"items": []}

    selected_asset = None
    selected_asset_value = request.GET.get("asset_id") or request.POST.get("asset_id")
    if selected_asset_value:
        try:
            selected_asset_uuid = UUID(selected_asset_value)
        except (TypeError, ValueError):
            return HttpResponse("معرف المعدة غير صالح", status=400)
        selected_asset = next(
            (
                asset for asset in assets["items"]
                if UUID(str(asset["id"])) == selected_asset_uuid
            ),
            None,
        )
        if selected_asset is None:
            return HttpResponse("المعدة غير متاحة ضمن النطاق المعروض", status=404)

    can_view_meters = _can(identity, "equipment.meters.view")
    can_record_meters = _can(identity, "equipment.meters.record")
    can_approve_meters = _can(identity, "equipment.meters.approve")
    can_view_fuel = _can(identity, "equipment.fuel.view")
    can_record_fuel = _can(identity, "equipment.fuel.record")
    can_approve_fuel = _can(identity, "equipment.fuel.approve")
    can_view_parts = _can(identity, "equipment.parts.view")
    can_view_reports = _can(identity, "equipment.reports.view")
    can_install_parts = (
        _can(identity, "equipment.parts.install")
        and _can(identity, "equipment.inventory.view")
        and _can(identity, "inventory.documents.view")
    )
    can_remove_parts = (
        _can(identity, "equipment.parts.remove")
        and _can(identity, "equipment.inventory.view")
        and _can(identity, "inventory.documents.view")
    )
    can_replace_parts = (
        _can(identity, "equipment.parts.replace")
        and _can(identity, "equipment.inventory.view")
        and _can(identity, "inventory.documents.view")
    )
    can_view_fuel_mappings = _can(identity, "equipment.inventory.view")
    can_manage_fuel_mappings = _can(identity, "equipment.inventory.manage")
    can_create_fuel_inventory_issue = (
        can_view_fuel_mappings
        and _can(identity, "equipment.fuel.record")
        and _can(identity, "inventory.documents.create")
        and _can(identity, "inventory.documents.view")
    )
    can_create_fuel_inventory_return = (
        can_record_fuel
        and _can(identity, "inventory.documents.create")
        and _can(identity, "inventory.documents.view")
    )
    fuel_inventory_mappings = {"items": []}
    fuel_inventory_items = {"items": []}
    fuel_inventory_warehouses = {"items": []}
    mapping_choices_available = (
        can_manage_fuel_mappings
        and _can(identity, "inventory.items.view")
        and _can(identity, "inventory.warehouses.view")
        and can_view_categories
        and bool(identity.get("organization_id"))
    )
    if can_view_fuel_mappings and identity.get("organization_id"):
        try:
            fuel_inventory_mappings = client.get(
                "/equipment/inventory/fuel-mappings",
                {"organization_id": identity["organization_id"]},
            )
        except UnauthorizedException:
            return redirect("auth:login")
        except ForbiddenException:
            return HttpResponse("ليس لديك صلاحية عرض إعدادات ربط الوقود بالمخزون", status=403)
        except ApiException:
            return HttpResponse("تعذر تحميل إعدادات ربط الوقود؛ حاول مجددًا", status=503)
    if mapping_choices_available:
        try:
            params = {"organization_id": identity["organization_id"], "limit": 200}
            fuel_inventory_items = client.get("/inventory/items", params)
            fuel_inventory_warehouses = client.get("/inventory/warehouses", params)
        except UnauthorizedException:
            return redirect("auth:login")
        except ForbiddenException:
            mapping_choices_available = False
        except ApiException:
            return HttpResponse("تعذر تحميل أصناف ومخازن Inventory؛ حاول مجددًا", status=503)
    meter_events = {"items": []}
    fuel_events = {"items": []}
    fuel_balance = {"items": []}
    if selected_asset and can_view_meters:
        try:
            meter_events = client.get(
                f"/equipment/assets/{selected_asset['id']}/meter-events"
            )
        except UnauthorizedException:
            return redirect("auth:login")
        except ForbiddenException:
            return HttpResponse("ليس لديك صلاحية عرض أحداث العداد", status=403)
        except NotFoundException:
            return HttpResponse("المعدة غير متاحة", status=404)
        except ApiException:
            return HttpResponse("تعذر تحميل أحداث العداد؛ حاول مجددًا", status=503)
    if selected_asset and can_view_fuel:
        try:
            fuel_events = client.get(
                f"/equipment/assets/{selected_asset['id']}/fuel-events"
            )
            fuel_balance = client.get(
                f"/equipment/assets/{selected_asset['id']}/fuel-balance"
            )
        except UnauthorizedException:
            return redirect("auth:login")
        except ForbiddenException:
            return HttpResponse("ليس لديك صلاحية عرض سجل الوقود", status=403)
        except NotFoundException:
            return HttpResponse("المعدة غير متاحة", status=404)
        except ApiException:
            return HttpResponse("تعذر تحميل سجل الوقود؛ حاول مجددًا", status=503)
    part_lifecycles = {"items": []}
    if selected_asset and can_view_parts:
        try:
            part_lifecycles = client.get(
                f"/equipment/assets/{selected_asset['id']}/part-lifecycles"
            )
        except UnauthorizedException:
            return redirect("auth:login")
        except ForbiddenException:
            return HttpResponse("ليس لديك صلاحية عرض دورة حياة قطع الغيار", status=403)
        except NotFoundException:
            return HttpResponse("المعدة غير متاحة", status=404)
        except ApiException:
            return HttpResponse("تعذر تحميل دورة حياة قطع الغيار؛ حاول مجددًا", status=503)
    actor_id = str(identity.get("id") or identity.get("user_id") or "").replace("-", "").lower()
    for event in meter_events["items"]:
        event["can_approve"] = (
            can_approve_meters
            and bool(actor_id)
            and event["status"] == "pending"
            and event["created_by"].replace("-", "").lower() != actor_id
        )
    for event in fuel_events["items"]:
        event["can_review"] = (
            can_approve_fuel
            and bool(actor_id)
            and event["status"] == "draft"
            and event["created_by"].replace("-", "").lower() != actor_id
        )
        event["can_create_inventory_issue"] = (
            can_create_fuel_inventory_issue
            and selected_asset is not None
            and event["event_type"] == "issued"
            and event["status"] in {"draft", "posted"}
            and any(
                mapping["is_active"]
                and mapping["energy_type"] == event["energy_type"]
                and mapping["category_id"].replace("-", "").lower()
                == selected_asset["category_id"].replace("-", "").lower()
                for mapping in fuel_inventory_mappings["items"]
            )
        )
        event["can_create_inventory_return"] = (
            can_create_fuel_inventory_return
            and event["event_type"] == "returned"
            and event["status"] == "posted"
            and bool(event.get("related_issue_event_id"))
        )

    can_view_movements = _can(identity, "equipment.movements.view")
    can_create_movements = _can(identity, "equipment.movements.create")
    can_dispatch_movements = _can(identity, "equipment.movements.dispatch")
    can_receive_movements = _can(identity, "equipment.movements.receive")
    can_cancel_movements = _can(identity, "equipment.movements.cancel")
    if can_view_movements:
        try:
            equipment_movements = client.get("/equipment/movements")
        except UnauthorizedException:
            return redirect("auth:login")
        except ForbiddenException:
            return HttpResponse("ليس لديك صلاحية عرض حركات المعدات", status=403)
        except NotFoundException:
            return HttpResponse("وحدة إدارة المعدات غير متاحة", status=404)
        except ApiException:
            return HttpResponse("تعذر تحميل حركات المعدات؛ حاول مجددًا", status=503)
    else:
        equipment_movements = {"items": []}

    can_view_inspections = _can(identity, "equipment.inspections.view")
    can_record_inspections = _can(identity, "equipment.inspections.record")
    can_verify_inspections = _can(identity, "equipment.inspections.verify")
    can_view_maintenance = _can(identity, "equipment.maintenance.view")
    can_create_maintenance = _can(identity, "equipment.maintenance.create")
    can_execute_maintenance = _can(identity, "equipment.maintenance.execute")
    can_release_safety = _can(identity, "equipment.safety.release")
    if can_view_inspections:
        try:
            inspections = client.get("/equipment/inspections")
        except UnauthorizedException:
            return redirect("auth:login")
        except ForbiddenException:
            return HttpResponse("ليس لديك صلاحية عرض الفحوص", status=403)
        except NotFoundException:
            return HttpResponse("وحدة إدارة المعدات غير متاحة", status=404)
        except ApiException:
            return HttpResponse("تعذر تحميل الفحوص؛ حاول مجددًا", status=503)
    else:
        inspections = {"items": []}
    if can_view_maintenance:
        try:
            maintenance_orders = client.get("/equipment/maintenance-orders")
        except UnauthorizedException:
            return redirect("auth:login")
        except ForbiddenException:
            return HttpResponse("ليس لديك صلاحية عرض أوامر الصيانة", status=403)
        except NotFoundException:
            return HttpResponse("وحدة إدارة المعدات غير متاحة", status=404)
        except ApiException:
            return HttpResponse("تعذر تحميل أوامر الصيانة؛ حاول مجددًا", status=503)
    else:
        maintenance_orders = {"items": []}
    if can_view_maintenance:
        try:
            maintenance_plans = client.get("/equipment/maintenance-plans")
            due_maintenance_plans = client.get("/equipment/maintenance-plans/due")
        except UnauthorizedException:
            return redirect("auth:login")
        except ForbiddenException:
            return HttpResponse("ليس لديك صلاحية عرض خطط الصيانة", status=403)
        except NotFoundException:
            return HttpResponse("وحدة إدارة المعدات غير متاحة", status=404)
        except ApiException:
            return HttpResponse("تعذر تحميل خطط الصيانة؛ حاول مجددًا", status=503)
    else:
        maintenance_plans = {"items": []}
        due_maintenance_plans = {"items": [], "blocked_items": []}
    verified_post_repair_inspections = [
        row for row in inspections["items"]
        if row["inspection_type"] == "post_repair"
        and row["result"] == "passed"
        and row["status"] == "verified"
    ]

    category_form = CategoryForm(request.POST or None)
    asset_form = AssetForm(request.POST or None, categories=categories["items"])
    movement_form = EquipmentMovementForm(request.POST or None, assets=assets["items"])
    inspection_form = InspectionForm(request.POST or None, assets=assets["items"])
    maintenance_form = MaintenanceForm(request.POST or None, assets=assets["items"])
    maintenance_plan_form = MaintenancePlanForm(request.POST or None, assets=assets["items"])
    meter_event_form = MeterEventForm(
        request.POST or None,
        initial={"asset_id": selected_asset["id"]} if selected_asset else None,
        assets=assets["items"],
        approved_readings=meter_events["items"],
    )
    fuel_event_form = FuelEventForm(
        request.POST or None,
        initial={"asset_id": selected_asset["id"]} if selected_asset else None,
        assets=assets["items"],
        issued_events=fuel_events["items"],
    )
    part_install_form = PartInstallForm(request.POST or None)
    part_removal_form = PartRemovalForm(request.POST or None)
    part_replacement_form = PartReplacementForm(request.POST or None)
    for lifecycle in part_lifecycles["items"]:
        removal_post = (
            request.POST
            if request.method == "POST"
            and request.POST.get("action") == "remove_part"
            and request.POST.get("lifecycle_id") == str(lifecycle["id"])
            else None
        )
        lifecycle["removal_form"] = PartRemovalForm(
            removal_post, initial={"lifecycle_id": lifecycle["id"]}
        )
        replacement_post = (
            request.POST
            if request.method == "POST"
            and request.POST.get("action") == "replace_part"
            and request.POST.get("lifecycle_id") == str(lifecycle["id"])
            else None
        )
        lifecycle["replacement_form"] = PartReplacementForm(
            replacement_post,
            initial={
                "lifecycle_id": lifecycle["id"],
                "inventory_item_id": lifecycle["inventory_item_id"],
                "mount_position": lifecycle["mount_position"],
            },
        )
    fuel_inventory_mapping_form = FuelInventoryMappingForm(
        request.POST or None,
        categories=categories["items"] if can_view_categories else [],
        items=fuel_inventory_items["items"],
        warehouses=fuel_inventory_warehouses["items"],
    )
    completion_form = MaintenanceCompletionForm(request.POST or None)
    inspection_release_form = SafetyReleaseForm(request.POST or None, inspections=inspections["items"])
    maintenance_release_form = SafetyReleaseForm(request.POST or None, inspections=inspections["items"])
    can_view_requests = _can(identity, "equipment.requests.view")
    can_create_requests = _can(identity, "equipment.requests.create")
    can_approve_requests = _can(identity, "equipment.requests.approve")
    can_reject_requests = _can(identity, "equipment.requests.reject")
    request_form = EquipmentRequestForm(request.POST or None, categories=categories["items"])
    if can_view_requests:
        try:
            equipment_requests = client.get("/equipment/requests")
        except UnauthorizedException:
            return redirect("auth:login")
        except ForbiddenException:
            return HttpResponse("ليس لديك صلاحية عرض طلبات المعدات", status=403)
        except NotFoundException:
            return HttpResponse("وحدة إدارة المعدات غير متاحة", status=404)
        except ApiException:
            return HttpResponse("تعذر تحميل طلبات المعدات؛ حاول مجددًا", status=503)
    else:
        equipment_requests = {"items": []}
    response_status = 200
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "create_category":
            category_form = CategoryForm(request.POST)
            form = category_form
            endpoint = "/equipment/categories"
            permission = "equipment.categories.manage"
        elif action == "create_asset":
            if not can_view_categories:
                return HttpResponse("تتطلب إضافة المعدة صلاحية عرض التصنيفات", status=403)
            asset_form = AssetForm(request.POST, categories=categories["items"])
            form = asset_form
            endpoint = "/equipment/assets"
            permission = "equipment.assets.manage"
        elif action == "create_request":
            if not can_view_categories:
                return HttpResponse("تتطلب إضافة الطلب صلاحية عرض التصنيفات", status=403)
            request_form = EquipmentRequestForm(request.POST, categories=categories["items"])
            form = request_form
            endpoint = "/equipment/requests"
            permission = "equipment.requests.create"
        elif action == "create_movement":
            if not can_view_assets:
                return HttpResponse("تتطلب إضافة حركة صلاحية عرض سجل المعدات", status=403)
            movement_form = EquipmentMovementForm(request.POST, assets=assets["items"])
            form = movement_form
            endpoint = "/equipment/movements"
            permission = "equipment.movements.create"
        elif action == "create_inspection":
            if not can_view_assets:
                return HttpResponse("تتطلب إضافة الفحص صلاحية عرض سجل المعدات", status=403)
            inspection_form = InspectionForm(request.POST, assets=assets["items"])
            form = inspection_form
            endpoint = "/equipment/inspections"
            permission = "equipment.inspections.record"
        elif action == "create_maintenance":
            if not can_view_assets:
                return HttpResponse("تتطلب إضافة الصيانة صلاحية عرض سجل المعدات", status=403)
            maintenance_form = MaintenanceForm(request.POST, assets=assets["items"])
            form = maintenance_form
            endpoint = "/equipment/maintenance-orders"
            permission = "equipment.maintenance.create"
        elif action == "create_maintenance_plan":
            if not can_view_assets:
                return HttpResponse("تتطلب جدولة الصيانة صلاحية عرض سجل المعدات", status=403)
            maintenance_plan_form = MaintenancePlanForm(request.POST, assets=assets["items"])
            form = maintenance_plan_form
            endpoint = "/equipment/maintenance-plans"
            permission = "equipment.maintenance.create"
        elif action == "create_meter_event":
            if not can_record_meters or not can_view_assets:
                return HttpResponse("ليس لديك صلاحية تسجيل أحداث العداد", status=403)
            meter_event_form = MeterEventForm(
                request.POST,
                assets=assets["items"],
                approved_readings=meter_events["items"],
            )
            form = meter_event_form
            endpoint = ""
            permission = "equipment.meters.record"
        elif action == "create_fuel_event":
            if not can_record_fuel or not can_view_assets:
                return HttpResponse("ليس لديك صلاحية تسجيل أحداث الوقود", status=403)
            fuel_event_form = FuelEventForm(
                request.POST,
                assets=assets["items"],
                issued_events=fuel_events["items"],
            )
            form = fuel_event_form
            endpoint = ""
            permission = "equipment.fuel.record"
        elif action == "install_part":
            if not selected_asset or not can_install_parts:
                return HttpResponse("تتطلب العملية صلاحية تركيب القطع وقراءة مستندات Inventory", status=403)
            part_install_form = PartInstallForm(request.POST)
            form = part_install_form
            endpoint = f"/equipment/assets/{selected_asset['id']}/part-lifecycles"
            permission = "equipment.parts.install"
        elif action == "remove_part":
            if not selected_asset or not can_remove_parts:
                return HttpResponse("تتطلب العملية صلاحية إزالة القطع وقراءة مستندات Inventory", status=403)
            part_removal_form = PartRemovalForm(request.POST)
            form = part_removal_form
            endpoint = ""
            permission = "equipment.parts.remove"
        elif action == "replace_part":
            if not selected_asset or not can_replace_parts:
                return HttpResponse("تتطلب العملية صلاحية استبدال القطع وقراءة مستندات Inventory", status=403)
            part_replacement_form = PartReplacementForm(request.POST)
            form = part_replacement_form
            endpoint = ""
            permission = "equipment.parts.replace"
        elif action == "save_fuel_inventory_mapping":
            if not can_manage_fuel_mappings or not mapping_choices_available:
                return HttpResponse("تتطلب إدارة الربط صلاحيات إعداد EMO وعرض أصناف ومخازن Inventory", status=403)
            fuel_inventory_mapping_form = FuelInventoryMappingForm(
                request.POST,
                categories=categories["items"],
                items=fuel_inventory_items["items"],
                warehouses=fuel_inventory_warehouses["items"],
            )
            form = fuel_inventory_mapping_form
            endpoint = ""
            permission = "equipment.inventory.manage"
        elif action == "create_fuel_inventory_issue":
            if not can_create_fuel_inventory_issue or not can_view_fuel:
                return HttpResponse("تتطلب العملية صلاحية الوقود وإنشاء وعرض مستندات Inventory", status=403)
            if selected_asset is None:
                return HttpResponse("يجب اختيار معدة من نطاق المؤسسة", status=422)
            try:
                event_id = UUID(request.POST.get("event_id", ""))
            except (TypeError, ValueError):
                return HttpResponse("معرف حدث الوقود غير صالح", status=400)
            event = next(
                (row for row in fuel_events["items"] if UUID(str(row["id"])) == event_id),
                None,
            )
            if (
                event is None or event["event_type"] != "issued"
                or event["status"] not in {"draft", "posted"}
            ):
                return HttpResponse("حدث الصرف غير متاح لإنشاء مستند مخزني", status=409)
            mapping = next(
                (
                    row for row in fuel_inventory_mappings["items"]
                    if row["is_active"]
                    and row["energy_type"] == event["energy_type"]
                    and row["category_id"].replace("-", "").lower()
                    == selected_asset["category_id"].replace("-", "").lower()
                ),
                None,
            )
            if mapping is None:
                return HttpResponse("لا يوجد ربط نشط مطابق لصنف الوقود والمخزن", status=409)
            try:
                document_date = event["event_at"].split("T", 1)[0]
                payload = {
                    "organization_id": identity["organization_id"],
                    "warehouse_id": mapping["warehouse_id"],
                    "document_type": "ISSUE_DIRECT",
                    "document_date": document_date,
                    "source_module": "equipment",
                    "source_type": "fuel_event",
                    "source_id": event_id.hex,
                    "lines": [{
                        "item_id": mapping["item_id"],
                        "quantity": event["quantity"],
                    }],
                }
                document = client.post("/inventory/documents", data=payload)
            except UnauthorizedException:
                return redirect("auth:login")
            except ForbiddenException as exc:
                return HttpResponse(str(exc), status=403)
            except NotFoundException as exc:
                return HttpResponse(str(exc), status=404)
            except ValidationException as exc:
                return HttpResponse(str(exc), status=422)
            except ConflictException as exc:
                return HttpResponse(str(exc), status=409)
            except ApiException:
                return HttpResponse("تعذر إنشاء مسودة الصرف في Inventory؛ حاول مجددًا", status=503)
            except (KeyError, TypeError, ValueError):
                return HttpResponse("بيانات حدث الوقود أو التاريخ غير صالحة", status=422)
            destination = reverse("inventory:operations") + "?" + urlencode({
                "mode": "documents",
                "warehouse_id": mapping["warehouse_id"],
                "document": document["id"],
            })
            return HttpResponseRedirect(destination)
        elif action == "create_fuel_inventory_return":
            if not can_create_fuel_inventory_return or not can_view_fuel:
                return HttpResponse("تتطلب العملية صلاحية الوقود وإنشاء وعرض مستندات Inventory", status=403)
            if selected_asset is None:
                return HttpResponse("يجب اختيار معدة من نطاق المؤسسة", status=422)
            try:
                event_id = UUID(request.POST.get("event_id", ""))
            except (TypeError, ValueError):
                return HttpResponse("معرف حدث الوقود غير صالح", status=400)
            event = next(
                (row for row in fuel_events["items"] if UUID(str(row["id"])) == event_id),
                None,
            )
            if (
                event is None or event["event_type"] != "returned"
                or event["status"] != "posted" or not event.get("related_issue_event_id")
            ):
                return HttpResponse("حدث المرتجع غير معتمد أو غير مرتبط بصرف أصلي", status=409)
            try:
                organization_id = urlencode({"organization_id": identity["organization_id"]})
                document = client.post(
                    f"/inventory/documents/equipment-fuel-returns/{event_id.hex}?{organization_id}"
                )
            except UnauthorizedException:
                return redirect("auth:login")
            except ForbiddenException as exc:
                return HttpResponse(str(exc), status=403)
            except NotFoundException as exc:
                return HttpResponse(str(exc), status=404)
            except ValidationException as exc:
                return HttpResponse(str(exc), status=422)
            except ConflictException as exc:
                return HttpResponse(str(exc), status=409)
            except ApiException:
                return HttpResponse("تعذر إنشاء مسودة المرتجع في Inventory؛ حاول مجددًا", status=503)
            destination = reverse("inventory:operations") + "?" + urlencode({
                "mode": "documents",
                "warehouse_id": document["warehouse_id"],
                "document": document["id"],
            })
            return HttpResponseRedirect(destination)
        elif action in ("approve_request", "reject_request"):
            permission = (
                "equipment.requests.approve" if action == "approve_request"
                else "equipment.requests.reject"
            )
            if not _can(identity, permission):
                return HttpResponse("ليس لديك صلاحية تنفيذ هذا الإجراء", status=403)
            try:
                request_id = UUID(request.POST.get("request_id", ""))
            except (TypeError, ValueError):
                return HttpResponse("معرف الطلب غير صالح", status=400)
            reason = request.POST.get("decision_reason", "").strip()
            if action == "reject_request" and not reason:
                return HttpResponse("سبب الرفض مطلوب", status=422)
            endpoint = f"/equipment/requests/{request_id}/{'approve' if action == 'approve_request' else 'reject'}"
            try:
                client.post(endpoint, data={"decision_reason": reason})
            except UnauthorizedException:
                return redirect("auth:login")
            except ForbiddenException:
                return HttpResponse("ليس لديك صلاحية تنفيذ هذا الإجراء", status=403)
            except NotFoundException:
                return HttpResponse("الطلب غير متاح", status=404)
            except ValidationException as exc:
                return HttpResponse(str(exc), status=422)
            except ConflictException as exc:
                return HttpResponse(str(exc), status=409)
            except ApiException:
                return HttpResponse("تعذر تحديث الطلب؛ حاول مجددًا", status=503)
            return redirect("/equipment/")
        elif action in ("dispatch_movement", "receive_movement", "cancel_movement"):
            permission = {
                "dispatch_movement": "equipment.movements.dispatch",
                "receive_movement": "equipment.movements.receive",
                "cancel_movement": "equipment.movements.cancel",
            }[action]
            if not _can(identity, permission):
                return HttpResponse("ليس لديك صلاحية تنفيذ هذا الإجراء", status=403)
            try:
                movement_id = UUID(request.POST.get("movement_id", ""))
            except (TypeError, ValueError):
                return HttpResponse("معرف حركة المعدة غير صالح", status=400)
            endpoint = f"/equipment/movements/{movement_id}/"
            endpoint += {
                "dispatch_movement": "dispatch",
                "receive_movement": "receive",
                "cancel_movement": "cancel",
            }[action]
            data = {}
            if action == "receive_movement":
                condition = request.POST.get("condition_at_receipt", "").strip()
                if not condition:
                    return HttpResponse("حالة المعدة عند الاستلام مطلوبة", status=422)
                data["condition_at_receipt"] = condition
            try:
                client.post(endpoint, data=data)
            except UnauthorizedException:
                return redirect("auth:login")
            except ForbiddenException:
                return HttpResponse("ليس لديك صلاحية تنفيذ هذا الإجراء", status=403)
            except NotFoundException:
                return HttpResponse("حركة المعدة غير متاحة", status=404)
            except ValidationException as exc:
                return HttpResponse(str(exc), status=422)
            except ConflictException as exc:
                return HttpResponse(str(exc), status=409)
            except ApiException:
                return HttpResponse("تعذر تحديث حركة المعدة؛ حاول مجددًا", status=503)
            return redirect("/equipment/")
        elif action in (
            "verify_inspection", "release_inspection", "complete_maintenance", "release_maintenance",
        ):
            permission_by_action = {
                "verify_inspection": "equipment.inspections.verify",
                "release_inspection": "equipment.safety.release",
                "complete_maintenance": "equipment.maintenance.execute",
                "release_maintenance": "equipment.safety.release",
            }
            permission = permission_by_action[action]
            if not _can(identity, permission):
                return HttpResponse("ليس لديك صلاحية تنفيذ هذا الإجراء", status=403)
            try:
                record_id = UUID(request.POST.get("record_id", ""))
            except (TypeError, ValueError):
                return HttpResponse("معرف السجل غير صالح", status=400)
            if action == "verify_inspection":
                endpoint = f"/equipment/inspections/{record_id}/verify"
                data = {}
            elif action == "complete_maintenance":
                endpoint = f"/equipment/maintenance-orders/{record_id}/complete"
                completion_form = MaintenanceCompletionForm(request.POST)
                if not completion_form.is_valid():
                    return HttpResponse("ملاحظات الإكمال الفني مطلوبة", status=422)
                data = completion_form.payload()
            elif action == "release_inspection":
                endpoint = f"/equipment/inspections/{record_id}/release-block"
                inspection_release_form = SafetyReleaseForm(request.POST, inspections=inspections["items"])
                if not inspection_release_form.is_valid():
                    return HttpResponse("اختر فحص ما بعد الإصلاح المتحقق", status=422)
                data = inspection_release_form.payload()
            else:
                endpoint = f"/equipment/maintenance-orders/{record_id}/release-block"
                maintenance_release_form = SafetyReleaseForm(request.POST, inspections=inspections["items"])
                if not maintenance_release_form.is_valid():
                    return HttpResponse("اختر فحص ما بعد الإصلاح المتحقق", status=422)
                data = maintenance_release_form.payload()
            try:
                client.post(endpoint, data=data)
            except UnauthorizedException:
                return redirect("auth:login")
            except ForbiddenException:
                return HttpResponse("ليس لديك صلاحية تنفيذ هذا الإجراء", status=403)
            except NotFoundException:
                return HttpResponse("السجل غير متاح", status=404)
            except ValidationException as exc:
                return HttpResponse(str(exc), status=422)
            except ConflictException as exc:
                return HttpResponse(str(exc), status=409)
            except ApiException:
                return HttpResponse("تعذر تحديث سجل السلامة؛ حاول مجددًا", status=503)
            return redirect("/equipment/")
        elif action in (
            "generate_maintenance_order", "pause_maintenance_plan", "resume_maintenance_plan",
        ):
            if not can_create_maintenance:
                return HttpResponse("ليس لديك صلاحية إدارة خطط الصيانة", status=403)
            try:
                plan_id = UUID(request.POST.get("plan_id", ""))
            except (TypeError, ValueError):
                return HttpResponse("معرف خطة الصيانة غير صالح", status=400)
            suffix = {
                "generate_maintenance_order": "orders",
                "pause_maintenance_plan": "pause",
                "resume_maintenance_plan": "resume",
            }[action]
            try:
                client.post(f"/equipment/maintenance-plans/{plan_id}/{suffix}")
            except UnauthorizedException:
                return redirect("auth:login")
            except ForbiddenException:
                return HttpResponse("ليس لديك صلاحية إدارة خطط الصيانة", status=403)
            except NotFoundException:
                return HttpResponse("خطة الصيانة غير متاحة", status=404)
            except ValidationException as exc:
                return HttpResponse(str(exc), status=422)
            except ConflictException as exc:
                return HttpResponse(str(exc), status=409)
            except ApiException:
                return HttpResponse("تعذر تحديث خطة الصيانة؛ حاول مجددًا", status=503)
            return redirect("/equipment/")
        elif action in ("approve_meter_event", "approve_fuel_event", "reject_fuel_event"):
            permission = (
                "equipment.meters.approve" if action == "approve_meter_event"
                else "equipment.fuel.approve"
            )
            if not _can(identity, permission):
                return HttpResponse("ليس لديك صلاحية مراجعة حدث المعدات", status=403)
            try:
                event_id = UUID(request.POST.get("event_id", ""))
            except (TypeError, ValueError):
                return HttpResponse("معرف الحدث غير صالح", status=400)
            if action == "approve_meter_event":
                endpoint = f"/equipment/meter-events/{event_id}/approve"
                data = {}
            elif action == "approve_fuel_event":
                endpoint = f"/equipment/fuel-events/{event_id}/approve"
                data = {"decision_reason": request.POST.get("decision_reason", "").strip()}
            else:
                reason = request.POST.get("decision_reason", "").strip()
                if not reason:
                    return HttpResponse("سبب رفض حدث الوقود مطلوب", status=422)
                endpoint = f"/equipment/fuel-events/{event_id}/reject"
                data = {"decision_reason": reason}
            try:
                client.post(endpoint, data=data)
            except UnauthorizedException:
                return redirect("auth:login")
            except ForbiddenException:
                return HttpResponse("ليس لديك صلاحية مراجعة حدث المعدات", status=403)
            except NotFoundException:
                return HttpResponse("حدث المعدات غير متاح", status=404)
            except ValidationException as exc:
                return HttpResponse(str(exc), status=422)
            except ConflictException as exc:
                return HttpResponse(str(exc), status=409)
            except ApiException:
                return HttpResponse("تعذر مراجعة الحدث؛ حاول مجددًا", status=503)
            return redirect(f"/equipment/?asset_id={request.POST.get('asset_id', '')}")
        else:
            return HttpResponse("إجراء غير معروف", status=400)
        if not _can(identity, permission):
            return HttpResponse("ليس لديك صلاحية تنفيذ هذا الإجراء", status=403)
        if form.is_valid():
            try:
                payload = form.payload()
                detail_asset_id = None
                if action == "create_meter_event":
                    detail_asset_id = meter_event_form.cleaned_data["asset_id"]
                    asset = next(
                        item for item in assets["items"]
                        if UUID(str(item["id"])) == UUID(detail_asset_id)
                    )
                    payload.pop("asset_id", None)
                    payload.update(
                        meter_type=asset["meter_type_locked"],
                        meter_unit=asset["meter_unit_locked"],
                    )
                    suffix = {
                        "reading": "meter-readings",
                        "replacement": "meter-replacements",
                        "correction": "meter-corrections",
                    }[meter_event_form.cleaned_data["event_type"]]
                    endpoint = f"/equipment/assets/{detail_asset_id}/{suffix}"
                elif action == "create_fuel_event":
                    detail_asset_id = fuel_event_form.cleaned_data["asset_id"]
                    payload.pop("asset_id", None)
                    endpoint = f"/equipment/assets/{detail_asset_id}/fuel-events"
                elif action == "install_part":
                    detail_asset_id = selected_asset["id"]
                elif action == "remove_part":
                    lifecycle_id = payload.pop("lifecycle_id")
                    endpoint = f"/equipment/part-lifecycles/{lifecycle_id}/remove"
                    detail_asset_id = selected_asset["id"]
                elif action == "replace_part":
                    lifecycle_id = payload.pop("lifecycle_id")
                    endpoint = f"/equipment/part-lifecycles/{lifecycle_id}/replace"
                    detail_asset_id = selected_asset["id"]
                if action == "save_fuel_inventory_mapping":
                    organization_id = identity.get("organization_id")
                    if not organization_id:
                        return HttpResponse("لا يمكن تحديد الجهة لهذا الحساب", status=422)
                    mapping_category = fuel_inventory_mapping_form.cleaned_data["category_id"]
                    mapping_energy = fuel_inventory_mapping_form.cleaned_data["energy_type"]
                    client.put(
                        f"/equipment/inventory/fuel-mappings/{mapping_category}/{mapping_energy}",
                        data={
                            "organization_id": organization_id,
                            "item_id": fuel_inventory_mapping_form.cleaned_data["item_id"],
                            "warehouse_id": fuel_inventory_mapping_form.cleaned_data["warehouse_id"],
                        },
                    )
                    return redirect("/equipment/")
                if action == "create_request":
                    org_id = identity.get("organization_id")
                    if not org_id:
                        return HttpResponse("لا يمكن تحديد الجهة الطالبة لهذا الحساب", status=422)
                    payload["requested_entity_id"] = str(org_id)
                elif action == "create_movement":
                    org_id = identity.get("organization_id")
                    if not org_id:
                        return HttpResponse("لا يمكن تحديد جهة الحركة لهذا الحساب", status=422)
                    payload.update(
                        from_entity_id=str(org_id),
                        to_entity_id=str(org_id),
                        idempotency_key=uuid4().hex,
                    )
                client.post(endpoint, data=payload)
            except UnauthorizedException:
                return redirect("auth:login")
            except ForbiddenException:
                return HttpResponse("ليس لديك صلاحية تنفيذ هذا الإجراء", status=403)
            except NotFoundException:
                return HttpResponse("مرجع التصنيف غير متاح", status=404)
            except ValidationException as exc:
                form.add_error(None, str(exc))
                response_status = 422
            except ConflictException as exc:
                form.add_error(None, str(exc))
                response_status = 409
            except ApiException:
                form.add_error(None, "تعذر حفظ البيانات؛ حاول مجددًا")
                response_status = 503
            else:
                if detail_asset_id:
                    return redirect(f"/equipment/?asset_id={detail_asset_id}")
                return redirect("/equipment/")

    return render(request, "equipment/home.html", {
        "identity": identity,
        "core_modules": modules,
        "dashboard": dashboard,
        "categories": categories["items"],
        "assets": assets["items"],
        "search": request.GET.get("search", ""),
        "category_form": category_form,
        "asset_form": asset_form,
        "request_form": request_form,
        "equipment_requests": equipment_requests["items"],
        "movement_form": movement_form,
        "equipment_movements": equipment_movements["items"],
        "can_manage_categories": _can(identity, "equipment.categories.manage"),
        "can_manage_assets": _can(identity, "equipment.assets.manage"),
        "can_view_assets": can_view_assets,
        "can_view_categories": can_view_categories,
        "can_view_requests": can_view_requests,
        "can_create_requests": can_create_requests,
        "can_approve_requests": can_approve_requests,
        "can_reject_requests": can_reject_requests,
        "can_view_movements": can_view_movements,
        "can_create_movements": can_create_movements,
        "can_dispatch_movements": can_dispatch_movements,
        "can_receive_movements": can_receive_movements,
        "can_cancel_movements": can_cancel_movements,
        "inspections": inspections["items"],
        "maintenance_orders": maintenance_orders["items"],
        "maintenance_plans": maintenance_plans["items"],
        "due_maintenance_plans": due_maintenance_plans["items"],
        "blocked_maintenance_plans": due_maintenance_plans.get("blocked_items", []),
        "inspection_form": inspection_form,
        "maintenance_form": maintenance_form,
        "maintenance_plan_form": maintenance_plan_form,
        "meter_events": meter_events["items"],
        "fuel_events": fuel_events["items"],
        "fuel_balance": fuel_balance["items"],
        "meter_event_form": meter_event_form,
        "fuel_event_form": fuel_event_form,
        "part_lifecycles": part_lifecycles["items"],
        "part_install_form": part_install_form,
        "part_removal_form": part_removal_form,
        "part_replacement_form": part_replacement_form,
        "can_view_parts": can_view_parts,
        "can_view_reports": can_view_reports,
        "can_install_parts": can_install_parts,
        "can_remove_parts": can_remove_parts,
        "can_replace_parts": can_replace_parts,
        "fuel_inventory_mapping_form": fuel_inventory_mapping_form,
        "fuel_inventory_mappings": fuel_inventory_mappings["items"],
        "can_view_fuel_mappings": can_view_fuel_mappings,
        "can_manage_fuel_mappings": can_manage_fuel_mappings,
        "can_create_fuel_inventory_issue": can_create_fuel_inventory_issue,
        "fuel_inventory_mapping_choices_available": mapping_choices_available,
        "selected_asset": selected_asset,
        "can_view_meters": can_view_meters,
        "can_record_meters": can_record_meters,
        "can_approve_meters": can_approve_meters,
        "can_view_fuel": can_view_fuel,
        "can_record_fuel": can_record_fuel,
        "can_approve_fuel": can_approve_fuel,
        "completion_form": completion_form,
        "inspection_release_form": inspection_release_form,
        "maintenance_release_form": maintenance_release_form,
        "verified_post_repair_inspections": verified_post_repair_inspections,
        "can_view_inspections": can_view_inspections,
        "can_record_inspections": can_record_inspections,
        "can_verify_inspections": can_verify_inspections,
        "can_view_maintenance": can_view_maintenance,
        "can_create_maintenance": can_create_maintenance,
        "can_execute_maintenance": can_execute_maintenance,
        "can_release_safety": can_release_safety,
    }, status=response_status)
