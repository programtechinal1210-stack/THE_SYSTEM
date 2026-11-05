"""UDE-03 isolated persistence lab.

All Core reads and writes stay server-side through the existing ApiClient.
The browser receives only a filtered snapshot and opaque concurrency token.
This view is not included in the production shell.
"""
import json

from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_protect

from shared.services.api_client import ApiClient, ApiException, ConflictException, ForbiddenException, UnauthorizedException, ValidationException

UDE_KEYS = {
    "core.ude.theme", "core.ude.palette", "core.ude.custom_colors",
    "core.ude.luminance_adjustment", "core.ude.font_family",
    "core.ude.font_scale", "core.ude.density", "core.ude.contrast",
    "core.ude.motion", "core.ude.sidebar",
}


def _profile(request):
    token = request.session.get("access_token")
    if not token:
        return None, {"error": "authentication_required"}
    try:
        payload = ApiClient(token=token).get("/settings-center", {"scope": "user"})
        items = payload.get("items", []) if isinstance(payload, dict) else []
        values = {item["key"]: item["value"] for item in items if item.get("key") in UDE_KEYS}
        return payload, {
            "schema_version": 1,
            "profile_version": payload.get("token", ""),
            "server_token": payload.get("token", ""),
            "values": values,
            "source": "core",
            "error": None,
        }
    except ApiException:
        return None, {"error": "core_unavailable", "source": "safe-default"}


def page(request):
    if not request.session.get("access_token"):
        return redirect("auth:login")
    _, profile = _profile(request)
    return render(request, "core/ude_03_lab.html", {"ude_profile": profile})


@csrf_protect
def save(request):
    if not request.session.get("access_token"):
        return JsonResponse({"error": "authentication_required"}, status=401)
    if request.method != "POST":
        return JsonResponse({"error": "method_not_allowed"}, status=405)
    try:
        body = json.loads(request.body or "{}")
        expected = body.get("expected")
        changes = body.get("changes")
        if not isinstance(expected, str) or not isinstance(changes, list) or not changes:
            return JsonResponse({"error": "invalid_request"}, status=422)
        if any(not isinstance(change, dict) or change.get("key") not in UDE_KEYS for change in changes):
            return JsonResponse({"error": "unsupported_key"}, status=422)
        payload = {"scope": "user", "expected": expected, "changes": changes, "confirmed": False, "reason": "UDE-03 lab"}
        result = ApiClient(token=request.session["access_token"]).post("/settings-center/batch", payload)
        return JsonResponse(result, status=200)
    except ConflictException:
        return JsonResponse({"error": "conflict"}, status=409)
    except UnauthorizedException:
        return JsonResponse({"error": "authentication_required"}, status=401)
    except ForbiddenException:
        return JsonResponse({"error": "forbidden"}, status=403)
    except ValidationException:
        return JsonResponse({"error": "invalid_preference"}, status=422)
    except ApiException:
        status = 502
        return JsonResponse({"error": "core_write_failed", "status": status}, status=status)
    except (TypeError, ValueError):
        return JsonResponse({"error": "invalid_json"}, status=422)
