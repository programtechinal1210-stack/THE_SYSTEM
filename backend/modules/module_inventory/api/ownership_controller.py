from uuid import UUID
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict
from typing import Literal
from sqlalchemy import text
from fastapi import HTTPException
from ..application.inventory_service import InventoryService, now
from infrastructure.database.db_context import get_session
from ..application.ownership_service import OwnershipService

router = APIRouter(prefix='/api/v1/inventory/warehouses', tags=['Inventory legal ownership'])
Session = Depends(get_session, scope='function')


class Owner(BaseModel):
    model_config = ConfigDict(extra='forbid')
    legal_entity_id: UUID


class Grant(BaseModel):
    model_config = ConfigDict(extra='forbid')
    user_id: UUID
    permission: Literal['inventory.documents.view','inventory.documents.create','inventory.documents.approve',
                        'inventory.documents.post','inventory.stock.view','inventory.reports.view',
                        'inventory.reservations.view','inventory.reservations.manage']
    enabled: bool = True


@router.put('/{warehouse_id}/access')
async def grant(warehouse_id: UUID, data: Grant, request: Request, session=Session):
    service = InventoryService(session, request)
    wh = await service._owned('warehouses', warehouse_id.hex, 'manage')
    if not await session.scalar(text("SELECT 1 FROM sqlite_master WHERE name='inv_warehouse_access'")):
        raise HTTPException(409, 'Operational reference migration has not been deployed')
    target = await service._reference('users', data.user_id.hex)
    if target['organization_id'] != wh['organization_id']:
        raise HTTPException(422, 'Warehouse delegate must belong to the operating organization')
    params = {'w': warehouse_id.hex, 'u': data.user_id.hex, 'p': data.permission,
              'by': request.state.user_id.hex, 'at': now()}
    if data.enabled:
        await session.execute(text('INSERT INTO inv_warehouse_access(warehouse_id,user_id,permission,granted_by,granted_at) '
            'VALUES(:w,:u,:p,:by,:at) ON CONFLICT(warehouse_id,user_id,permission) DO NOTHING'), params)
    else:
        await session.execute(text('DELETE FROM inv_warehouse_access WHERE warehouse_id=:w AND user_id=:u AND permission=:p'), params)
    request.state.audit_details = {'entity_type': 'inventory.warehouse_access', 'entity_id': warehouse_id.hex,
        'new': {'user_id': data.user_id.hex, 'permission': data.permission, 'enabled': data.enabled}}
    return {'warehouse_id': warehouse_id.hex, 'user_id': data.user_id.hex, 'permission': data.permission, 'enabled': data.enabled}


@router.get('/{warehouse_id}/readiness')
async def readiness(warehouse_id: UUID, request: Request, session=Session):
    return await OwnershipService(session, request).readiness(warehouse_id.hex)


@router.put('/{warehouse_id}/owner')
async def assign(warehouse_id: UUID, data: Owner, request: Request, session=Session):
    return await OwnershipService(session, request).assign(warehouse_id.hex, data.legal_entity_id.hex)
