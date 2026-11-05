from uuid import UUID, uuid4

from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from shared.services.api_client import (
    ApiClient,
    ApiException,
    ConflictException,
    ForbiddenException,
    NotFoundException,
    UnauthorizedException,
    ValidationException,
)
from .operation_forms import (
    AuthorityReferenceForm,
    OperationFinishForm,
    OperationStartForm,
    SafetyPolicyForm,
)


def _can(identity, permission):
    return identity.get("is_admin", False) or permission in identity.get("permissions", [])


def _api_error(exc):
    if isinstance(exc, UnauthorizedException):
        return redirect("auth:login")
    if isinstance(exc, ForbiddenException):
        return HttpResponse("ليس لديك صلاحية تنفيذ هذا الإجراء", status=403)
    if isinstance(exc, NotFoundException):
        return HttpResponse("السجل المطلوب غير متاح", status=404)
    if isinstance(exc, ValidationException):
        return HttpResponse(str(exc), status=422)
    if isinstance(exc, ConflictException):
        return HttpResponse(str(exc), status=409)
    return HttpResponse("تعذر الاتصال بخدمة المعدات؛ حاول مجددًا", status=503)


@require_http_methods(["GET", "POST"])
def equipment_operations(request):
    client = ApiClient(token=request.session.get("access_token"))
    try:
        identity = client.get("/auth/me")
    except (UnauthorizedException, ForbiddenException, NotFoundException, ApiException) as exc:
        return _api_error(exc)

    can_view_policies = _can(identity, "equipment.safety_policy.view")
    can_manage_policies = _can(identity, "equipment.safety_policy.manage")
    can_approve_policies = _can(identity, "equipment.safety_policy.approve")
    can_view_operations = _can(identity, "equipment.operations.view")
    can_start_operations = _can(identity, "equipment.operations.start")
    can_record_operations = _can(identity, "equipment.operations.record")
    can_verify_operations = _can(identity, "equipment.operations.verify")
    can_approve_meters = _can(identity, "equipment.meters.approve")

    policies = {"items": []}
    operations = {"items": []}
    assignments = {"items": []}
    rosters = {"items": []}
    if can_view_policies and identity.get("organization_id"):
        try:
            policies = client.get(
                "/equipment/safety-policies",
                {"organization_id": identity["organization_id"]},
            )
        except (UnauthorizedException, ForbiddenException, NotFoundException, ApiException) as exc:
            return _api_error(exc)
    if can_view_operations and identity.get("organization_id"):
        try:
            operations = client.get(
                "/equipment/operations",
                {"organization_id": identity["organization_id"]},
            )
        except (UnauthorizedException, ForbiddenException, NotFoundException, ApiException) as exc:
            return _api_error(exc)
    can_load_start_choices = (
        can_start_operations
        and _can(identity, "equipment.assignments.view")
        and _can(identity, "hr.shift.view")
    )
    if can_load_start_choices:
        try:
            assignments = client.get("/equipment/assignments")
            rosters = client.get("/hr/shift-roster")
        except (UnauthorizedException, ForbiddenException, NotFoundException, ApiException) as exc:
            return _api_error(exc)

    action = request.POST.get("action", "") if request.method == "POST" else ""
    policy_form = SafetyPolicyForm(
        request.POST if action == "create_policy" else None
    )
    start_form = OperationStartForm(
        request.POST if action == "start_operation" else None,
        assignments=assignments["items"],
        rosters=rosters["items"],
        policies=policies["items"],
    )
    decision_form = AuthorityReferenceForm(
        request.POST if action in ("approve_policy", "withdraw_policy") else None
    )
    finish_forms = {
        operation["id"]: OperationFinishForm(
            request.POST
            if action == "finish_operation"
            and request.POST.get("operation_id") == operation["id"]
            else None
        )
        for operation in operations["items"] if operation["status"] == "running"
    }

    if request.method == "POST":
        if action == "create_policy":
            if not can_manage_policies:
                return HttpResponse("ليس لديك صلاحية تسجيل سياسة السلامة", status=403)
            policy_form = SafetyPolicyForm(request.POST)
            if not policy_form.is_valid():
                return _render(request, identity, policies, operations, assignments, rosters,
                               policy_form, start_form, decision_form, finish_forms,
                               can_load_start_choices, can_manage_policies, can_approve_policies,
                               can_start_operations, can_record_operations, can_verify_operations,
                               can_view_policies, can_view_operations, status=422)
            try:
                organization_id = identity.get("organization_id")
                if not organization_id:
                    return HttpResponse("لا يمكن تحديد الجهة لهذا الحساب", status=422)
                client.post(
                    "/equipment/safety-policies",
                    data=policy_form.payload(organization_id),
                )
            except (UnauthorizedException, ForbiddenException, NotFoundException,
                    ValidationException, ConflictException, ApiException) as exc:
                return _api_error(exc)
            return redirect("equipment:operations")
        if action in ("approve_policy", "withdraw_policy"):
            if not can_approve_policies:
                return HttpResponse("ليس لديك صلاحية اعتماد سياسة السلامة", status=403)
            decision_form = AuthorityReferenceForm(request.POST)
            if not decision_form.is_valid():
                return _render(request, identity, policies, operations, assignments, rosters,
                               policy_form, start_form, decision_form, finish_forms,
                               can_load_start_choices, can_manage_policies, can_approve_policies,
                               can_start_operations, can_record_operations, can_verify_operations,
                               can_view_policies, can_view_operations, status=422)
            try:
                policy_id = UUID(request.POST.get("policy_id", ""))
            except (TypeError, ValueError):
                return HttpResponse("معرف سياسة السلامة غير صالح", status=400)
            suffix = "approve" if action == "approve_policy" else "withdraw"
            try:
                client.post(
                    f"/equipment/safety-policies/{policy_id}/{suffix}",
                    data=decision_form.cleaned_data,
                )
            except (UnauthorizedException, ForbiddenException, NotFoundException,
                    ValidationException, ConflictException, ApiException) as exc:
                return _api_error(exc)
            return redirect("equipment:operations")
        if action == "start_operation":
            if not can_load_start_choices:
                return HttpResponse("تتطلب بداية التشغيل صلاحية عرض التكليفات والورديات", status=403)
            start_form = OperationStartForm(
                request.POST, assignments=assignments["items"],
                rosters=rosters["items"], policies=policies["items"],
            )
            if not start_form.is_valid():
                return _render(request, identity, policies, operations, assignments, rosters,
                               policy_form, start_form, decision_form, finish_forms,
                               can_load_start_choices, can_manage_policies, can_approve_policies,
                               can_start_operations, can_record_operations, can_verify_operations,
                               can_view_policies, can_view_operations, status=422)
            try:
                client.post(
                    "/equipment/operations",
                    data=start_form.payload(uuid4().hex),
                )
            except (UnauthorizedException, ForbiddenException, NotFoundException,
                    ValidationException, ConflictException, ApiException) as exc:
                return _api_error(exc)
            return redirect("equipment:operations")
        if action == "finish_operation":
            if not can_record_operations:
                return HttpResponse("ليس لديك صلاحية إقفال التشغيل", status=403)
            try:
                operation_id = UUID(request.POST.get("operation_id", ""))
            except (TypeError, ValueError):
                return HttpResponse("معرف سجل التشغيل غير صالح", status=400)
            finish_form = OperationFinishForm(request.POST)
            finish_forms[operation_id.hex] = finish_form
            if not finish_form.is_valid():
                return _render(request, identity, policies, operations, assignments, rosters,
                               policy_form, start_form, decision_form, finish_forms,
                               can_load_start_choices, can_manage_policies, can_approve_policies,
                               can_start_operations, can_record_operations, can_verify_operations,
                               can_view_policies, can_view_operations, status=422)
            try:
                client.post(
                    f"/equipment/operations/{operation_id}/finish",
                    data=finish_form.payload(),
                )
            except (UnauthorizedException, ForbiddenException, NotFoundException,
                    ValidationException, ConflictException, ApiException) as exc:
                return _api_error(exc)
            return redirect("equipment:operations")
        if action == "verify_operation":
            if not can_verify_operations:
                return HttpResponse("ليس لديك صلاحية التحقق من سجل التشغيل", status=403)
            try:
                operation_id = UUID(request.POST.get("operation_id", ""))
            except (TypeError, ValueError):
                return HttpResponse("معرف سجل التشغيل غير صالح", status=400)
            try:
                client.post(f"/equipment/operations/{operation_id}/verify")
            except (UnauthorizedException, ForbiddenException, NotFoundException,
                    ValidationException, ConflictException, ApiException) as exc:
                return _api_error(exc)
            return redirect("equipment:operations")
        if action == "approve_operation_meter":
            if not can_approve_meters:
                return HttpResponse("ليس لديك صلاحية اعتماد قراءة العداد", status=403)
            try:
                meter_event_id = UUID(request.POST.get("meter_event_id", ""))
            except (TypeError, ValueError):
                return HttpResponse("معرف حدث العداد غير صالح", status=400)
            linked_event = any(
                operation.get("meter_end_event_id") == meter_event_id.hex
                and operation.get("meter_end_event_status") == "pending"
                for operation in operations["items"]
            )
            if not linked_event:
                return HttpResponse("حدث العداد غير متاح للاعتماد ضمن سجلات التشغيل", status=404)
            try:
                client.post(f"/equipment/meter-events/{meter_event_id}/approve")
            except (UnauthorizedException, ForbiddenException, NotFoundException,
                    ValidationException, ConflictException, ApiException) as exc:
                return _api_error(exc)
            return redirect("equipment:operations")
        return HttpResponse("إجراء غير معروف", status=400)

    return _render(request, identity, policies, operations, assignments, rosters,
                   policy_form, start_form, decision_form, finish_forms,
                   can_load_start_choices, can_manage_policies, can_approve_policies,
                   can_start_operations, can_record_operations, can_verify_operations,
                   can_view_policies, can_view_operations)


def _render(request, identity, policies, operations, assignments, rosters,
            policy_form, start_form, decision_form, finish_forms,
            can_load_start_choices, can_manage_policies, can_approve_policies,
            can_start_operations, can_record_operations, can_verify_operations,
            can_view_policies, can_view_operations, status=200):
    status_labels = {
        "running": "تعمل الآن",
        "submitted": "بانتظار المراجعة",
        "verified": "مكتمل ومعتمد",
    }
    asset_by_id = {}
    assignment_by_id = {str(row.get("id")): row for row in assignments.get("items", [])}
    for operation in operations["items"]:
        operation["finish_form"] = finish_forms.get(operation["id"])
        assignment = assignment_by_id.get(str(operation.get("assignment_id")), {})
        operation["asset_name"] = operation.get("asset_name") or assignment.get("asset_name") or "معدة غير محددة"
        operation["asset_code"] = operation.get("asset_code") or assignment.get("asset_code") or operation.get("asset_id", "—")
        operation["operator_name"] = operation.get("operator_name") or assignment.get("operator_name") or operation.get("operator_employee_id", "غير محدد")
        operation["status_label"] = status_labels.get(operation.get("status"), "غير محددة")
    search = request.GET.get("search", "").strip().casefold()
    status_filter = request.GET.get("status", "").strip()
    filtered_operations = operations["items"]
    if search:
        filtered_operations = [row for row in filtered_operations if search in " ".join(
            str(row.get(key, "")) for key in ("operation_code", "asset_name", "asset_code", "operator_name")
        ).casefold()]
    if status_filter in status_labels:
        filtered_operations = [row for row in filtered_operations if row.get("status") == status_filter]
    selected_id = request.GET.get("operation_id", "").strip()
    selected_operation = next((row for row in operations["items"] if str(row.get("id")) == selected_id), None)
    page_size = 12
    try:
        page = max(1, int(request.GET.get("page", "1")))
    except (TypeError, ValueError):
        page = 1
    page_count = max(1, (len(filtered_operations) + page_size - 1) // page_size)
    page = min(page, page_count)
    visible_operations = filtered_operations[(page - 1) * page_size:page * page_size]
    start_ready_count = sum(
        bool(row.get("eligible_to_start") or row.get("ready_to_start"))
        for row in assignments.get("items", [])
    )
    active_count = sum(row.get("status") == "running" for row in operations["items"])
    review_count = sum(row.get("status") == "submitted" for row in operations["items"])
    completed_count = sum(row.get("status") == "verified" for row in operations["items"])
    return render(request, "equipment/operations.html", {
        "identity": identity,
        "core_modules": [],
        "policies": policies["items"],
        "operations": visible_operations,
        "all_operations": operations["items"],
        "selected_operation": selected_operation,
        "assignments": assignments["items"],
        "rosters": rosters["items"],
        "total": len(filtered_operations), "page": page, "page_count": page_count,
        "counts": {"ready": start_ready_count, "running": active_count, "review": review_count, "completed": completed_count},
        "status_labels": status_labels,
        "create_mode": request.GET.get("create") == "1" or bool(start_form.errors),
        "policy_form": policy_form,
        "start_form": start_form,
        "decision_form": decision_form,
        "finish_forms": finish_forms,
        "can_load_start_choices": can_load_start_choices,
        "can_manage_policies": can_manage_policies,
        "can_approve_policies": can_approve_policies,
        "can_start_operations": can_start_operations,
        "can_record_operations": can_record_operations,
        "can_verify_operations": can_verify_operations,
        "can_approve_meters": _can(identity, "equipment.meters.approve"),
        "can_view_policies": can_view_policies,
        "can_view_operations": can_view_operations,
    }, status=status)
