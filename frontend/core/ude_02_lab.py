"""Isolated UDE-02 server-side bootstrap lab.

This view deliberately reuses Django's existing authenticated ApiClient. It
never exposes access/refresh tokens and never writes settings.
"""
from django.shortcuts import render, redirect

from shared.services.api_client import ApiClient, ApiException


DEFAULTS = {
    "theme": "light",
    "density": "comfortable",
    "fontSize": 16,
    "fontFamily": "Tajawal",
    "contrast": "normal",
}
ALLOWED_FONTS = {"Tajawal", "Almarai", "IBM Plex Sans Arabic"}
ALLOWED_THEMES = {"light", "dark", "system", "high-contrast"}


def _safe_value(settings, key, value):
    if key == "theme" and value in ALLOWED_THEMES:
        settings[key] = value
    elif key == "density" and value in {"compact", "comfortable"}:
        settings[key] = value
    elif key == "fontSize" and type(value) is int and 12 <= value <= 24:
        settings[key] = value
    elif key == "fontFamily" and value in ALLOWED_FONTS:
        settings[key] = value
    elif key == "contrast" and value in {"normal", "high"}:
        settings[key] = value


def _bootstrap_from_core(request):
    """Read only approved appearance fields for the current session user."""
    bootstrap = {
        "schema": "ude.theme-bootstrap.v1",
        "source": "safe-default",
        "settings": dict(DEFAULTS),
        "rejected": [],
        "error": None,
    }
    token = request.session.get("access_token")
    if not token:
        return bootstrap | {"error": "authentication_required"}

    try:
        rows = ApiClient(token=token).get("/user-settings/effective")
        settings = dict(DEFAULTS)
        mapping = {
            "theme": "theme",
            "density": "density",
            "font_size": "fontSize",
            "font_family": "fontFamily",
            "contrast": "contrast",
        }
        for row in rows if isinstance(rows, list) else []:
            key = mapping.get(row.get("setting_key"))
            if not key:
                continue
            value = row.get("value")
            before = settings[key]
            _safe_value(settings, key, value)
            if settings[key] == before and value != before:
                bootstrap["rejected"].append(row.get("setting_key"))
        if settings["contrast"] == "high":
            settings["theme"] = "high-contrast"
        return bootstrap | {"source": "core", "settings": settings}
    except ApiException:
        return bootstrap | {"error": "core_unavailable"}


def page(request):
    if not request.session.get("access_token"):
        return redirect("auth:login")
    return render(request, "core/ude_02_lab.html", {"ude_bootstrap": _bootstrap_from_core(request)})
