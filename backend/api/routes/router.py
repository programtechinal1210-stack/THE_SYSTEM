from fastapi import APIRouter

from modules.module_users.api import (
    auth_router,
    users_router,
    roles_router,
    permissions_router,
)
from modules.module_settings.api.settings_controller import router as settings_router
from modules.module_settings.api.user_settings_controller import router as user_settings_router
from modules.module_settings.api.notification_settings_controller import router as notification_settings_router
from modules.module_notifications.api.notifications_controller import router as notifications_router
from modules.module_organizations.api.organizations_controller import router as organizations_router



router = APIRouter()
from modules.module_settings.api.center_controller import router as settings_center_router
router.include_router(settings_center_router)

# Identity & Access
router.include_router(auth_router)
router.include_router(users_router)
router.include_router(roles_router)
router.include_router(permissions_router)

# Institutional Core
router.include_router(organizations_router, prefix="/api/v1/organizations")
router.include_router(settings_router, prefix="/api/v1/settings")
router.include_router(user_settings_router, prefix="/api/v1/user-settings")
router.include_router(
    notification_settings_router,
    prefix="/api/v1/user-notification-settings",
)
router.include_router(notifications_router, prefix="/api/v1/notifications")

# Audit / Governance
from api.routes.audit.core_audit import router as core_audit_router
router.include_router(core_audit_router)
# Optional followups and legacy analytics remain unmounted until their own
# authorization and entity-reference contracts pass acceptance.

__all__ = ["router"]
from api.routes.modules import router as modules_router
from modules.module_organizations.api.org_units_controller import router as units_router
router.include_router(modules_router)
router.include_router(units_router)
router.include_router(organizations_router, prefix="/api/v1/entities")

from modules.module_users.api.account_controller import router as accounts_router
router.include_router(accounts_router)
from api.routes.references import router as references_router
router.include_router(references_router)

from modules.module_currency.api.currency_controller import router as currency_router
router.include_router(currency_router, prefix="/api/v1/currency")
from api.routes.recycle import router as recycle_router
router.include_router(recycle_router)
from api.routes.work_context import router as work_context_router
router.include_router(work_context_router)
from api.routes.legal_entities import router as legal_entities_router
router.include_router(legal_entities_router)
