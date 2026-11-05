"""UDE-05 pilot flag resolution; production remains disabled by default."""
import json
from pathlib import Path

from django.conf import settings


FLAG_FILE = Path(settings.BASE_DIR) / "shared" / "static" / "ude" / "ude-05-feature-flags-v1.0.0.json"
PILOT_PERMISSION = "core.settings.view"


def _read_flag():
    try:
        return json.loads(FLAG_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"enabled": False, "production_load": False}


def _has_pilot_permission(identity):
    """Reuse Core authorization; UDE does not define a parallel permission."""
    if not isinstance(identity, dict):
        return False
    return bool(identity.get("is_admin") or PILOT_PERMISSION in identity.get("permissions", []))


def use_pilot(request, identity=None):
    """Use Pilot only with a live Django session and an approved Core permission."""
    flag = _read_flag()
    authenticated = bool(request.session.get("access_token"))
    authorized = _has_pilot_permission(identity)
    if not authenticated or not authorized:
        return False
    if flag.get("enabled") is True and flag.get("production_load") is False:
        return True
    return (
        request.GET.get("ude_preview") == "1"
        and request.META.get("REMOTE_ADDR") in {"127.0.0.1", "::1"}
    )
