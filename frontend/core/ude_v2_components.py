"""Server-side gate for the scoped UDE V2 shared-components bridge."""
import json
from pathlib import Path

from django.conf import settings

from .ude_v2_flags import use_shared_shell


FLAG_FILE = Path(settings.BASE_DIR) / "shared" / "static" / "ude" / "ude-v2-shared-components-feature-flags-v1.0.0.json"


def read_flag():
    try:
        return json.loads(FLAG_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"enabled": False, "production_load": False, "pilot_usernames": []}


def _username(identity):
    if not isinstance(identity, dict):
        return ""
    return str(identity.get("username") or identity.get("user_name") or identity.get("login") or "")


def use_shared_components(request, identity=None, shell_enabled=False):
    """Enable components only behind the shell gate and an explicit pilot allowlist."""
    flag = read_flag()
    if not shell_enabled or flag.get("enabled") is not True or flag.get("production_load") is True:
        return False
    if not request.session.get("access_token") or not isinstance(identity, dict):
        return False
    permissions = identity.get("permissions") or []
    authorized = bool(identity.get("is_admin") or "core.settings.view" in permissions)
    pilots = {str(value) for value in (flag.get("pilot_usernames") or [])}
    return authorized and _username(identity) in pilots
