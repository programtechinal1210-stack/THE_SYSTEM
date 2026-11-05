from fastapi import HTTPException
from sqlalchemy import text
from core.access import require, allowed
from .inventory_service import InventoryService


async def warehouse(session, request, identifier, permission):
    require(request, permission)
    service = InventoryService(session, request)
    row = await service.repo.get('warehouses', identifier)
    if not row or row['deleted_at'] or not service._allows_org(row, permission):
        raise HTTPException(404, 'Warehouse outside authorized scope')
    await service._check_org(row['organization_id'])
    institution = 'institution' in request.state.permission_global_scopes.get(permission, set())
    if not request.state.is_admin and not institution:
        grant = await session.scalar(text('SELECT 1 FROM inv_warehouse_access WHERE warehouse_id=:w AND user_id=:u AND permission=:p'),
            {'w': identifier, 'u': request.state.user_id.hex, 'p': permission})
        if not grant:
            raise HTTPException(403, 'WAREHOUSE_FORBIDDEN')
    if row['status'] != 'active':
        raise HTTPException(409, 'WAREHOUSE_NOT_ACTIVE')
    return row


def costs(request, organization_id=None):
    from core.work_context import organization_allowed
    return allowed(request, 'inventory.costs.view') and (
        organization_id is None or organization_allowed(request, 'inventory.costs.view', organization_id))
