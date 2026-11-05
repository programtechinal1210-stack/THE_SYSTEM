from datetime import date
from uuid import UUID
from urllib.parse import urlencode

from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET

from shared.services.api_client import (
    ApiClient, ApiException, ForbiddenException, NotFoundException,
    UnauthorizedException, ValidationException, ConflictException,
)


def _can(identity, permission):
    return identity.get("is_admin", False) or permission in identity.get("permissions", [])


def _client(request):
    client = ApiClient(token=request.session.get("access_token"))
    try:
        identity = client.get("/auth/me")
    except UnauthorizedException:
        return None, redirect("auth:login")
    except ForbiddenException:
        return None, HttpResponse("ليس لديك صلاحية الوصول إلى تقارير المعدات", status=403)
    except ApiException:
        return None, HttpResponse("تعذر تحميل هوية المستخدم؛ حاول مجددًا", status=503)
    return (client, identity), None


def _filters(request, identity):
    organization_id = identity.get("organization_id")
    if not organization_id:
        raise ValueError("المستخدم غير مرتبط بنطاق مؤسسة للتقرير.")
    start_date = request.GET.get("start_date") or date.today().isoformat()
    end_date = request.GET.get("end_date") or date.today().isoformat()
    try:
        date.fromisoformat(start_date)
        date.fromisoformat(end_date)
        asset_id = request.GET.get("asset_id", "").strip()
        if asset_id:
            asset_id = UUID(asset_id).hex
    except (TypeError, ValueError):
        raise ValueError("فترة التقرير أو معرف المعدة غير صالح.") from None
    params = {
        "organization_id": organization_id,
        "start_date": start_date,
        "end_date": end_date,
    }
    if asset_id:
        params["asset_id"] = asset_id
    return params


@require_GET
def equipment_reports(request):
    result, error = _client(request)
    if error:
        return error
    client, identity = result
    if not _can(identity, "equipment.reports.view"):
        return HttpResponse("ليس لديك صلاحية عرض تقارير المعدات", status=403)
    try:
        params = _filters(request, identity)
    except ValueError as exc:
        return HttpResponse(str(exc), status=422)
    try:
        report = client.get("/equipment/reports/analytics", params)
    except UnauthorizedException:
        return redirect("auth:login")
    except ForbiddenException:
        return HttpResponse("ليس لديك صلاحية عرض تقارير المعدات أو نطاقها", status=403)
    except NotFoundException:
        return HttpResponse("المعدة غير متاحة ضمن النطاق", status=404)
    except ValidationException as exc:
        return HttpResponse(str(exc), status=422)
    except ApiException:
        return HttpResponse("تعذر تحميل التقرير؛ حاول مجددًا", status=503)
    return render(request, "equipment/reports.html", {
        "report": report,
        "params": params,
        "can_view_costs": _can(identity, "equipment.costs.view"),
        "can_export": _can(identity, "equipment.reports.export"),
        "export_query": urlencode(params),
    })


@require_GET
def equipment_reports_export(request):
    result, error = _client(request)
    if error:
        return error
    client, identity = result
    if not _can(identity, "equipment.reports.export"):
        return HttpResponse("ليس لديك صلاحية تصدير تقارير المعدات", status=403)
    try:
        params = _filters(request, identity)
    except ValueError as exc:
        return HttpResponse(str(exc), status=422)
    try:
        content, media_type, disposition = client.download(
            "/equipment/reports/analytics.xlsx", params
        )
    except UnauthorizedException:
        return redirect("auth:login")
    except ForbiddenException:
        return HttpResponse("ليس لديك صلاحية تصدير هذا التقرير أو نطاقه", status=403)
    except NotFoundException:
        return HttpResponse("المعدة غير متاحة ضمن النطاق", status=404)
    except ConflictException as exc:
        return HttpResponse(str(exc), status=409)
    except ValidationException as exc:
        return HttpResponse(str(exc), status=422)
    except ApiException:
        return HttpResponse("تعذر تصدير التقرير؛ حاول مجددًا", status=503)
    response = HttpResponse(content, content_type=media_type)
    if disposition:
        response["Content-Disposition"] = disposition
    return response
