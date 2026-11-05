"""Server-side gate for the UDE V2 Shared Shell layer.

The flag is deliberately independent from the UDE-05 Core Home Pilot flag.
It reuses Core identity/permission data and never grants access from a URL.
"""
import json
from pathlib import Path

from django.conf import settings


FLAG_FILE = Path(settings.BASE_DIR) / "shared" / "static" / "ude" / "ude-v2-shared-shell-feature-flags-v1.0.0.json"
REQUIRED_PERMISSION = "core.settings.view"


def read_flag():
    try:
        return json.loads(FLAG_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"enabled": False, "production_load": False, "pilot_usernames": []}


def _identity_username(identity):
    if not isinstance(identity, dict):
        return ""
    return str(identity.get("username") or identity.get("user_name") or identity.get("login") or "")


def use_shared_shell(request, identity=None):
    """Return true only for an explicitly enabled, Core-authorized pilot user."""
    flag = read_flag()
    if flag.get("enabled") is not True or flag.get("production_load") is True:
        return False
    if not request.session.get("access_token") or not isinstance(identity, dict):
        return False
    permissions = identity.get("permissions") or []
    authorized = bool(identity.get("is_admin") or REQUIRED_PERMISSION in permissions)
    usernames = {str(value) for value in (flag.get("pilot_usernames") or [])}
    return authorized and _identity_username(identity) in usernames

