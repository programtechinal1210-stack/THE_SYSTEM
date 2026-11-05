"""Compatibility routes backed exclusively by the current user's API session."""
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.views.decorators.http import require_POST, require_GET
from shared.services.api_client import ApiClient, ApiException, NotFoundException, UnauthorizedException, ForbiddenException, ValidationException


def failure(exc):
    status = next((code for kind, code in ((NotFoundException, 404), (UnauthorizedException, 401),
                  (ForbiddenException, 403), (ValidationException, 422)) if isinstance(exc, kind)), 502)
    return JsonResponse({"detail": str(exc)}, status=status)


@require_GET
def detail(request, notif_id):
    try:
        item = ApiClient().get("/notifications/" + str(notif_id))
        return render(request, "notifications/detail.html", {"notification": item, "section": "notifications"})
    except ApiException as exc:
        return failure(exc)


@require_POST
def mark_read(request, notif_id):
    try:
        ApiClient().put("/notifications/mark-read/" + str(notif_id))
        return redirect("notifications:list")
    except ApiException as exc:
        return failure(exc)


@require_POST
def mark_all_read(request):
    try:
        ApiClient().put("/notifications/mark-all-read")
        return redirect("notifications:list")
    except ApiException as exc:
        return failure(exc)


@require_GET
def bell(request):
    try:
        return JsonResponse(ApiClient().get("/notifications/unread-count"))
    except ApiException as exc:
        return failure(exc)


@require_GET
def listing(request):
    try:
        return JsonResponse({"items": ApiClient().get("/notifications", {"unread": request.GET.get("unread") == "1"})})
    except ApiException as exc:
        return failure(exc)
