# config/urls.py
# Core-only URL map after business-module extraction.

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import FileResponse, HttpResponseNotFound

from core import views as core_views
from core import workspace
from core import settings_center
from core import currency
from core import work_context
from core import ude_02_lab
from core import ude_03_lab
from core import ude_04_lab

import os


def serve_upload(request, file_path):
    """Serve existing uploaded files during the Core transition."""
    from pathlib import Path
    from shared.services.api_client import ApiClient, ApiException
    from django.http import HttpResponseForbidden

    try:
        if not ApiClient(token=request.session.get("access_token")).get("/auth/me").get("is_admin"):
            return HttpResponseForbidden("File access requires administrator permission")
    except ApiException:
        return HttpResponseForbidden("Authentication required")

    root = Path(getattr(settings, "UPLOAD_ROOT", settings.MEDIA_ROOT)).resolve()
    target = (root / file_path).resolve()
    if not target.is_relative_to(root) or not target.is_file():
        return HttpResponseNotFound("File not found")
    return FileResponse(target.open("rb"), as_attachment=True)


urlpatterns = [
    path('work-context/', work_context.choose, name='work_context'),
    path("currency/", currency.page, name="currency"),
    path("", workspace.page, {"section": "home"}, name="core_home"),
    path("users/", workspace.page, {"section": "users"}),
    path("users/roles/", workspace.page, {"section": "roles"}),
    path("users/export/core/", workspace.audit_export, {"resource": "users"}),
    path("users/profile/", workspace.page, {"section": "profile"}),
    path("organizations/tree/", workspace.page, {"section": "units"}),
    # Keep the historical URL as a compatible alias for the unified workspace.
    path("organizations/", workspace.page, {"section": "units"}),
    path("settings/", settings_center.page),
    path("settings/center/action/", settings_center.action),
    path("settings/center/<str:category>/", settings_center.page),
    path("ude-02/lab/", ude_02_lab.page, name="ude_02_lab"),
    path("ude-03/lab/", ude_03_lab.page, name="ude_03_lab"),
    path("ude-03/lab/save/", ude_03_lab.save, name="ude_03_lab_save"),
    path("ude-04/lab/", ude_04_lab.page, name="ude_04_lab"),
    path("notifications/", workspace.page, {"section": "notifications"}),
    path("audit/", workspace.page, {"section": "audit"}),
    path("audit/export/core/", workspace.audit_export),
    path("health/", core_views.health_check, name="health_check"),
    path("admin/", admin.site.urls),
    path("auth/", include("modules.module_auth.urls")),
    path("users/", include("modules.module_users.urls")),
    path("organizations/", include("modules.module_organizations.urls")),
    path("notifications/", include("modules.module_notifications.urls")),
    path("settings/", include("modules.module_settings.urls")),
    path("audit/", include("modules.module_audit.urls")),
    path("pm/", include("modules.module_pm.urls")),
    path("daily-work/", include("modules.module_daily_work.urls")),
    path("equipment/", include("modules.module_equipment.urls")),
    path("hr/", include("modules.module_hr.urls")),
    path("inventory/", include("modules.module_inventory.urls")),
    path("files/<path:file_path>", serve_upload, name="serve_upload"),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
 
