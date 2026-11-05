"""Inventory module manifest for application composition root."""
from core.module_registry import ModuleManifest
from .api.inventory_controller import router as inventory_router
from .api.ownership_controller import router as ownership_router
from .api.documents_controller import router as documents_router
from .api.stocktakes_controller import router as stocktakes_router
from .api.requests_controller import router as requests_router

manifest = ModuleManifest(
    code="inventory", name="إدارة المخازن", href="/inventory/", permission="inventory.items.view",
    version="0.3.0", enabled=True, api_prefixes=("/api/v1/inventory",), routers=(stocktakes_router, requests_router, documents_router, ownership_router, inventory_router),
    entity_types=('inventory.items', 'inventory.categories', 'inventory.warehouses', 'inventory.units', 'inventory.locations'),
    notification_templates={'inventory.request_approved': {'title': 'اعتماد طلب مخزني', 'body': 'تم اعتماد الطلب {doc} '}},
    permissions=("inventory.access",
                 "inventory.units.view", "inventory.units.manage",
                 "inventory.categories.view", "inventory.categories.manage",
                 "inventory.items.view", "inventory.items.manage",
                 "inventory.warehouses.view", "inventory.warehouses.manage",
                 'inventory.documents.view', 'inventory.documents.create', 'inventory.documents.approve',
                 'inventory.documents.post', 'inventory.documents.reverse', 'inventory.documents.close', 'inventory.stock.view', 'inventory.costs.view',
                 'inventory.reports.view', 'inventory.finance.configure', 'inventory.valuation.correct',
                 'inventory.stocktakes.view','inventory.stocktakes.create','inventory.stocktakes.count','inventory.stocktakes.approve','inventory.stocktakes.settle',
                 'inventory.requests.view','inventory.requests.create','inventory.requests.approve',
                 'inventory.reservations.view','inventory.reservations.manage'),
)
