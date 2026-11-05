# core/urls.py
# Secondary Core URL map. Kept clean so it can be reused if ROOT_URLCONF changes.

from django.urls import path, include
from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("health/", views.health_check, name="health"),
    path("users/", include("modules.module_users.urls")),
    path("organizations/", include("modules.module_organizations.urls")),
    path("notifications/", include("modules.module_notifications.urls")),
    path("settings/", include("modules.module_settings.urls")),
    path("audit/", include("modules.module_audit.urls")),
]