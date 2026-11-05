from django.urls import path
from .operations import equipment_operations
from .meters import equipment_meters
from .inspections import equipment_inspections
from .maintenance import equipment_maintenance
from .views import (
    equipment_asset_create,
    equipment_asset_detail,
    equipment_assets,
    equipment_home,
    equipment_requests,
    equipment_assignments,
    equipment_movements,
)
from .reports import equipment_reports, equipment_reports_export

app_name = "equipment"
urlpatterns = [
    path("", equipment_home, name="home"),
    path("assets/", equipment_assets, name="assets"),
    path("assets/new/", equipment_asset_create, name="asset-create"),
    path("assets/<uuid:asset_id>/", equipment_asset_detail, name="asset-detail"),
    path("requests/", equipment_requests, name="requests"),
    path("assignments/", equipment_assignments, name="assignments"),
    path("movements/", equipment_movements, name="movements"),
    path("operations/", equipment_operations, name="operations"),
    path("meters/", equipment_meters, name="meters"),
    path("inspections/", equipment_inspections, name="inspections"),
    path("maintenance/", equipment_maintenance, name="maintenance"),
    path("reports/", equipment_reports, name="reports"),
    path("reports/export/", equipment_reports_export, name="reports-export"),
]
