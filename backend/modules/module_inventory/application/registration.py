"""Owner callbacks installed only by the application's composition root."""
from uuid import UUID
from .inventory_service import InventoryService, permission


def register_entities(registry):
    for kind in ('units', 'categories', 'items', 'warehouses'):
        register_kind(registry, kind)
    register_locations(registry)


def register_locations(registry):
    from sqlalchemy import text
    from .inventory_service import in_scope

    async def owner(session, actor, admin, scopes, entity_id):
        row = (await session.execute(text(
            'SELECT l.*,w.organization_id FROM inv_locations l JOIN inv_warehouses w ON w.id=l.warehouse_id WHERE l.id=:i'),
            {'i': UUID(str(entity_id)).hex})).mappings().first()
        return dict(row) if row and in_scope(dict(row), actor, admin, scopes) else None

    async def authorize(session, actor, admin, scopes, entity_id):
        row = await owner(session, actor, admin, scopes, entity_id)
        return bool(row and row['deleted_at'])

    async def resolve(session, actor, admin, scopes, entity_id):
        row = await owner(session, actor, admin, scopes, entity_id)
        if row and not row['deleted_at']:
            return {'label': row['name'], 'href': '/inventory/?section=locations&warehouse_id=' + row['warehouse_id']}

    async def restore(session, entity_id, actor_id):
        await InventoryService(session).recover_location(UUID(str(entity_id)).hex, actor_id)

    async def purge(session, entity_id, actor_id):
        await InventoryService(session).recover_location(UUID(str(entity_id)).hex, actor_id, purge=True)

    registry.register_entity('inventory', 'inventory.locations', permission('warehouses', 'view'), resolve)
    registry.register_recycle('inventory', 'inventory.locations',
        {'view': permission('warehouses', 'view'), 'restore': permission('warehouses', 'manage'),
         'purge': permission('warehouses', 'manage')}, authorize, restore, purge)


def register_kind(registry, kind):
    async def owner(session, actor, admin, scopes, entity_id):
        row = await InventoryService(session).repo.get(kind, UUID(str(entity_id)).hex)
        if row is None:
            return None, None
        from .inventory_service import in_scope
        ok = True if kind == 'units' else in_scope(row, actor, admin, scopes)
        return (row, row) if ok else (None, None)

    async def authorize(session, actor, admin, scopes, entity_id):
        row, _ = await owner(session, actor, admin, scopes, entity_id)
        return bool(row and row.get('deleted_at'))

    async def resolve(session, actor, admin, scopes, entity_id):
        row, _ = await owner(session, actor, admin, scopes, entity_id)
        if not row or row.get('deleted_at'):
            return None
        return {'label': row.get('name') or row.get('name_ar') or row.get('code'),
                'href': '/inventory/'}

    async def restore(session, entity_id, actor_id):
        await InventoryService(session).recover(kind, UUID(str(entity_id)).hex, actor_id)

    async def purge(session, entity_id, actor_id):
        await InventoryService(session).recover(kind, UUID(str(entity_id)).hex, actor_id, purge=True)

    registry.register_entity('inventory', 'inventory.' + kind, permission(kind, 'view'), resolve)
    registry.register_recycle('inventory', 'inventory.' + kind,
        {'view': permission(kind, 'view'), 'restore': permission(kind, 'manage'),
         'purge': permission(kind, 'manage')},
        authorize, restore, purge)
