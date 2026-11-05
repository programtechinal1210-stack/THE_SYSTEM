"""Fail-closed dispatch to owning modules, using both Core and entity scopes."""
from fastapi import HTTPException
from sqlalchemy import text
from core.access import allowed
from core.module_registry import registry
from core import soft_delete
from modules.module_settings.application.module_policy import enabled_modules


async def authorized(session, request, row, action):
    handler = registry.recycle_handlers.get(row['entity_type'])
    if handler is None:
        return None
    module, permissions, authorize, restore, purge = handler
    if not (await enabled_modules(session)).get(module):
        return None
    permission = permissions[action]
    core_permission = 'core.recycle.view' if action == 'view' else 'core.recycle.manage'
    if not allowed(request, permission) or not allowed(request, core_permission):
        return None
    for code in (core_permission, permission):
        scopes = request.state.permission_scopes.get(code, {'self'})
        if not await authorize(session, request.state.user, request.state.is_admin, scopes, row['entity_id']):
            return None
    return handler


async def list_visible(session, request, entity_type, skip, limit):
    # Filter BEFORE pagination. Unregistered types expose neither metadata nor counts.
    result = []
    visible = 0
    offset = 0
    while True:
        rows = await soft_delete.list_deleted(session, entity_type, offset, 200)
        for row in rows:
            if await authorized(session, request, row, 'view'):
                if visible >= skip:
                    result.append(row)
                visible += 1
                if len(result) == limit:
                    return result
        if len(rows) < 200:
            return result
        offset += 200


async def mutate(session, request, bin_id, action):
    row = (await session.execute(text('SELECT * FROM recycle_bin WHERE id=:id AND restored_at IS NULL'),
                                 {'id': bin_id})).mappings().first()
    handler = await authorized(session, request, row, action) if row else None
    if handler is None:
        raise HTTPException(404, 'Entity unavailable within assigned scope')
    callback = handler[3] if action == 'restore' else handler[4]
    # Owner mutation first; Core updates its index only after successful validation.
    await callback(session, row['entity_id'], request.state.user.id)
    if action == 'restore':
        await soft_delete.restore(session, row['entity_type'], row['entity_id'], request.state.user.id)
    else:
        await soft_delete.purge(session, bin_id)
    request.state.audit_details = {'entity_type': row['entity_type'], 'entity_id': row['entity_id'],
                                   'old': {'deleted': True}, 'new': {'operation': action}}
