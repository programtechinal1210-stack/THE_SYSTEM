"""EMO manifest registered at the Core composition root."""
from core.module_registry import ModuleManifest
from .api.equipment_controller import router

manifest = ModuleManifest(
    code="equipment",
    name="إدارة المعدات",
    href="/equipment/",
    permission="equipment.access",
    version="0.1.0",
    enabled=True,
    api_prefixes=("/api/v1/equipment",),
    routers=(router,),
    permissions=(
        "equipment.access",
        "equipment.categories.view", "equipment.categories.manage",
        "equipment.assets.view", "equipment.assets.manage",
        "equipment.assignments.view", "equipment.assignments.create", "equipment.assignments.approve",
        "equipment.requests.view", "equipment.requests.create",
        "equipment.requests.approve", "equipment.requests.reject",
        "equipment.movements.view", "equipment.movements.create",
        "equipment.movements.dispatch", "equipment.movements.receive", "equipment.movements.cancel",
        "equipment.inspections.view", "equipment.inspections.record", "equipment.inspections.verify",
        "equipment.maintenance.view", "equipment.maintenance.create", "equipment.maintenance.execute",
        "equipment.safety.release",
        "equipment.meters.view", "equipment.meters.record", "equipment.meters.approve",
        "equipment.fuel.view", "equipment.fuel.record", "equipment.fuel.approve",
        "equipment.inventory.view", "equipment.inventory.manage",
        "equipment.safety_policy.view", "equipment.safety_policy.manage", "equipment.safety_policy.approve",
        "equipment.operations.view", "equipment.operations.start",
        "equipment.operations.record", "equipment.operations.verify", "equipment.operations.correct",
        "equipment.parts.view", "equipment.parts.install", "equipment.parts.remove",
        "equipment.parts.replace",
        "equipment.reports.view", "equipment.reports.export", "equipment.costs.view",
    ),
)
