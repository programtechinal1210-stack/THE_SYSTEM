from django.urls import path
from .operations import equipment_operations
from .views import (
    equipment_asset_create,
    equipment_asset_detail,
    equipment_assets,
    equipment_home,
    equipment_requests,
)
from .reports import equipment_reports, equipment_reports_export

app_name = "equipment"
urlpatterns = [
    path("", equipment_home, name="home"),
    path("assets/", equipment_assets, name="assets"),
    path("assets/new/", equipment_asset_create, name="asset-create"),
    path("assets/<uuid:asset_id>/", equipment_asset_detail, name="asset-detail"),
    path("requests/", equipment_requests, name="requests"),
    path("operations/", equipment_operations, name="operations"),
    path("reports/", equipment_reports, name="reports"),
    path("reports/export/", equipment_reports_export, name="reports-export"),
]
