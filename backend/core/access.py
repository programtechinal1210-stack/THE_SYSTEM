"""Central permission policy shared by APIs and navigation."""
from fastapi import HTTPException


def allowed(request, code):
    return bool(getattr(request.state, "is_admin", False) or code in getattr(request.state, "permissions", set()))


def require(request, code):
    if not allowed(request, code):
        raise HTTPException(403, "Permission denied")


def unit_scope(request, permission):
    if getattr(request.state, "is_admin", False):
        return None
    global_scopes = getattr(request.state, "permission_global_scopes", {})
    scopes = global_scopes.get(permission, set())
    if "institution" in scopes:
        return None
    if "organization" in scopes:
        return None
    return set(getattr(request.state, "permission_unit_scopes", {}).get(permission, set()))


def unit_allowed(request, permission, unit_id):
    scopes = unit_scope(request, permission)
    return scopes is None or (unit_id is not None and str(unit_id) in scopes)


def check_user_scope(request, target):
    if getattr(request.state, "is_admin", False):
        return
    scopes = getattr(request.state, "scopes", {"self"})
    actor = request.state.user
    if "institution" in scopes or ("organization" in scopes and target.organization_id == actor.organization_id):
        return
    if target.id == actor.id:
        return
    raise HTTPException(403, "Outside assigned data scope")


def route_permission(path, method):
    resource = path.removeprefix("/api/v1/").split("/")[0]
    read = method in ("GET", "HEAD")
    if resource == "auth":
        return "core.users.manage" if path.endswith("/register") else None
    if resource == "notifications":
        return "core.notifications.manage" if path.endswith("/send") else None
    if resource in ("user-settings", "user-notification-settings", "modules", "profile"):
        return None
    resource = {"org-units": "organizations", "entities": "organizations"}.get(resource, resource)
    if resource == 'legal-entities':
        return 'core.legal_entities.' + ('view' if read else 'manage')
    if resource == "inventory":
        sub = path.removeprefix("/api/v1/inventory").strip("/").split("/")[0] if path != "/api/v1/inventory" else ""
        if sub not in ('units', 'categories', 'items', 'warehouses', 'health'):
            return 'inventory.access'
        collection = sub if sub in ("units", "categories", "items", "warehouses") else "items"
        return f"inventory.{collection}.{'view' if read else 'manage'}"
    if resource == "equipment":
        sub = path.removeprefix("/api/v1/equipment").strip("/").split("/")[0]
        parts = path.removeprefix("/api/v1/equipment").strip("/").split("/")
        if sub == "asset-form-options":
            return "equipment.assets.manage"
        action = parts[-1] if len(parts) > 1 else ""
        if sub == "inventory":
            return "equipment.inventory.view" if read else "equipment.inventory.manage"
        if sub == "safety-policies":
            if read:
                return "equipment.safety_policy.view"
            return (
                "equipment.safety_policy.approve"
                if action in ("approve", "withdraw")
                else "equipment.safety_policy.manage"
            )
        if sub == "operations":
            if read:
                return "equipment.operations.view"
            if action == "verify":
                return "equipment.operations.verify"
            if action == "finish":
                return "equipment.operations.record"
            if action == "correct":
                return "equipment.operations.correct"
            return "equipment.operations.start"
        if sub == "reports":
            return (
                "equipment.reports.export"
                if len(parts) > 1 and parts[-1].endswith(".xlsx")
                else "equipment.reports.view"
            )
        if sub == "meter-events":
            return "equipment.meters.approve" if action == "approve" else (
                "equipment.meters.view" if read else "equipment.meters.record"
            )
        if sub == "fuel-events":
            if action in ("approve", "reject"):
                return "equipment.fuel.approve"
            return "equipment.fuel.view" if read else "equipment.fuel.record"
        if sub == "assets" and any(part in ("meter-events", "meter-readings",
                                             "meter-replacements", "meter-corrections")
                                   for part in parts):
            return "equipment.meters.view" if read else "equipment.meters.record"
        if sub == "assets" and any(part in ("fuel-events", "fuel-balance") for part in parts):
            return "equipment.fuel.view" if read else "equipment.fuel.record"
        if sub == "assignments":
            if action == "approve":
                return "equipment.assignments.approve"
            return "equipment.assignments.view" if read else "equipment.assignments.create"
        if sub == "requests":
            if action == "approve":
                return "equipment.requests.approve"
            if action == "reject":
                return "equipment.requests.reject"
            return "equipment.requests.view" if read else "equipment.requests.create"
        if sub == "movements":
            if action == "dispatch":
                return "equipment.movements.dispatch"
            if action == "receive":
                return "equipment.movements.receive"
            if action == "cancel":
                return "equipment.movements.cancel"
            return "equipment.movements.view" if read else "equipment.movements.create"
        if sub == "assets" and "movements" in parts:
            return "equipment.movements.view"
        if sub == "inspections":
            if action == "release-block":
                return "equipment.safety.release"
            if action == "verify":
                return "equipment.inspections.verify"
            return "equipment.inspections.view" if read else "equipment.inspections.record"
        if sub == "maintenance-orders":
            if action == "release-block":
                return "equipment.safety.release"
            if action == "complete":
                return "equipment.maintenance.execute"
            return "equipment.maintenance.view" if read else "equipment.maintenance.create"
        if sub == "maintenance-plans":
            return "equipment.maintenance.view" if read else "equipment.maintenance.create"
        if sub == "assets" and "assignments" in parts:
            return "equipment.assignments.view"
        collection = "categories" if sub == "categories" else "assets"
        return f"equipment.{collection}.{'view' if read else 'manage'}"
    if resource in {"users", "roles", "permissions", "organizations", "settings", "audit", "followups", "currency", "recycle"}:
        return f"core.{resource}.{'view' if read else 'manage'}"
    return None
