from fastapi import APIRouter, Depends, Request, Query
from pydantic import ValidationError
from infrastructure.database.db_context import get_session
from ..domain.catalog import Unit, Category, Item, ItemUnit, Warehouse, Location
from ..application.inventory_service import InventoryService
from uuid import UUID
from fastapi import HTTPException

router = APIRouter(prefix='/api/v1/inventory', tags=['Inventory'])
Session = Depends(get_session, scope='function')
MODELS = {'units': Unit, 'categories': Category, 'items': Item, 'warehouses': Warehouse}


def _parse_payload(model, values):
    try:
        return model.model_validate(values)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors(include_context=False)) from exc


@router.get('/health')
async def health():
    return {'module': 'inventory', 'status': 'ready', 'version': '0.1.0'}


@router.get('/{kind}')
async def list_kind(kind: str, request: Request, session=Session, organization_id: UUID | None = None,
                    search: str | None = None, skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200),
                    category_id: UUID | None = None, is_active: bool | None = None,
                    item_type: str | None = None):
    if kind not in MODELS:
        raise HTTPException(404, 'Unknown collection')
    if category_id is not None or is_active is not None or item_type is not None:
        if kind != 'items':
            raise HTTPException(422, 'Catalog filters are only available for items')
        if item_type is not None and item_type not in {'MATERIAL', 'SPARE_PART', 'CONSUMABLE', 'TOOL', 'OTHER'}:
            raise HTTPException(422, 'Unknown item type')
    return await InventoryService(session, request).list(
        kind, organization_id.hex if organization_id else None, search, skip, limit,
        category_id.hex if category_id else None, is_active, item_type)


@router.post('/{kind}', status_code=201)
async def create_kind(kind: str, request: Request, session=Session):
    if kind not in MODELS:
        from fastapi import HTTPException
        raise HTTPException(404, 'Unknown collection')
    body = await request.json()
    payload = _parse_payload(MODELS[kind], body)
    return await InventoryService(session, request).create(kind, payload)


@router.get('/{kind}/{entity_id}')
async def detail_kind(kind: str, entity_id: UUID, request: Request, session=Session):
    if kind not in MODELS:
        from fastapi import HTTPException
        raise HTTPException(404, 'Unknown collection')
    return await InventoryService(session, request).detail(kind, entity_id.hex)


@router.put('/{kind}/{entity_id}')
async def update_kind(kind: str, entity_id: UUID, request: Request, session=Session):
    if kind not in MODELS:
        raise HTTPException(404, 'Unknown collection')
    service = InventoryService(session, request)
    current = await service.detail(kind, entity_id.hex)
    merged = dict(current)
    changes = await request.json()
    if not isinstance(changes, dict) or set(changes) - set(MODELS[kind].model_fields):
        raise HTTPException(422, 'Unknown inventory fields')
    if 'organization_id' in changes:
        try:
            proposed_org = UUID(str(changes['organization_id'])).hex
        except (ValueError, TypeError, AttributeError):
            raise HTTPException(422, 'Invalid organization') from None
        if proposed_org != current['organization_id']:
            raise HTTPException(422, 'Organization cannot change')
    merged.update(changes)
    for f in ('id', 'created_at', 'updated_at', 'deleted_at', 'deleted_by'):
        merged.pop(f, None)
    payload = _parse_payload(
        MODELS[kind],
        {k: merged[k] for k in MODELS[kind].model_fields if k in merged},
    )
    return await service.update(kind, entity_id.hex, payload)


@router.delete('/{kind}/{entity_id}')
async def delete_kind(kind: str, entity_id: UUID, request: Request, session=Session):
    if kind not in MODELS:
        from fastapi import HTTPException
        raise HTTPException(404, 'Unknown collection')
    await InventoryService(session, request).delete(kind, entity_id.hex)
    return {'deleted': True}


@router.get('/warehouses/{warehouse_id}/locations')
async def list_locations(warehouse_id: UUID, request: Request, session=Session):
    return await InventoryService(session, request).list_locations(warehouse_id.hex)


@router.post('/warehouses/{warehouse_id}/locations', status_code=201)
async def create_location(warehouse_id: UUID, request: Request, session=Session):
    payload = _parse_payload(Location, await request.json())
    return await InventoryService(session, request).create_location(warehouse_id.hex, payload)


@router.put('/warehouses/{warehouse_id}/locations/{location_id}')
async def update_location(warehouse_id: UUID, location_id: UUID, request: Request, session=Session):
    payload = _parse_payload(Location, await request.json())
    return await InventoryService(session, request).update_location(warehouse_id.hex, location_id.hex, payload)


@router.delete('/warehouses/{warehouse_id}/locations/{location_id}')
async def delete_location(warehouse_id: UUID, location_id: UUID, request: Request, session=Session):
    await InventoryService(session, request).delete_location(warehouse_id.hex, location_id.hex)
    return {'deleted': True}


@router.get('/items/{item_id}/units')
async def list_item_units(item_id: UUID, request: Request, session=Session):
    return await InventoryService(session, request).list_item_units(item_id.hex)


@router.post('/items/{item_id}/units', status_code=201)
async def add_item_unit(item_id: UUID, request: Request, session=Session):
    payload = _parse_payload(ItemUnit, await request.json())
    return await InventoryService(session, request).add_item_unit(item_id.hex, payload)
