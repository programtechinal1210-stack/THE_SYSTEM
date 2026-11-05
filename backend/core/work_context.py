"""Personal organization context. Selecting a context never grants access."""
import json
from uuid import UUID, uuid4
from fastapi import HTTPException
from sqlalchemy import text


def uid(value):
    try:
        return UUID(str(value)).hex
    except (TypeError, ValueError, AttributeError):
        raise HTTPException(422, 'Invalid organization identifier') from None


def organization_allowed(request, permission, organization_id):
    organization_id = uid(organization_id)
    if request.state.is_admin:
        return True
    scopes = getattr(request.state, 'permission_global_scopes', {}).get(permission, set())
    if 'institution' in scopes:
        return True
    if 'organization' in scopes and organization_id == uid(request.state.user.organization_id):
        return True
    return organization_id in {uid(i) for i in getattr(request.state, 'permission_unit_scopes', {}).get(permission, set())}


async def options(session, request):
    rows = (await session.execute(text('SELECT id,name FROM organizations WHERE is_active=1 ORDER BY name,id'))).mappings().all()
    broad = request.state.is_admin or any('institution' in s for s in getattr(request.state, 'permission_global_scopes', {}).values())
    permitted = {uid(request.state.user.organization_id)} if request.state.user.organization_id else set()
    for units in getattr(request.state, 'permission_unit_scopes', {}).values():
        permitted.update(uid(i) for i in units)
    return [dict(r) for r in rows if broad or r['id'] in permitted]


async def context(session, request):
    permitted = await options(session, request)
    ids = {r['id'] for r in permitted}
    personal = await session.scalar(text('SELECT value FROM user_settings WHERE user_id=:u AND setting_key=:k'),
                                    {'u': request.state.user_id.hex, 'k': 'current_organization'})
    try:
        personal = json.loads(personal) if personal else None
    except (TypeError, ValueError):
        personal = None
    from modules.module_settings.application.center_service import system_value
    institutional = await session.scalar(text("SELECT value FROM setting_overrides WHERE setting_key='core.default_organization' AND scope_type='institution' AND scope_id=''"))
    try:
        default = json.loads(institutional) if institutional else await system_value(session, 'core.default_organization')
    except (TypeError, ValueError):
        default = None
    candidates = [(personal, 'personal'), (default, 'institution'),
                  (str(request.state.user.organization_id or '').replace('-', ''), 'membership')]
    for value, source in candidates:
        normalized = str(value or '').replace('-', '')
        if normalized in ids:
            return {'selected_id': normalized, 'source': source, 'items': permitted}
    return {'selected_id': permitted[0]['id'] if permitted else None,
            'source': 'available' if permitted else 'unavailable', 'items': permitted}


async def select(session, request, organization_id):
    chosen = uid(organization_id)
    if chosen not in {r['id'] for r in await options(session, request)}:
        raise HTTPException(403, 'Organization not available within assigned scope')
    old = await context(session, request)
    await session.execute(text('INSERT INTO user_settings(id,user_id,setting_key,value) VALUES(:id,:u,:k,:v) '
        'ON CONFLICT(user_id,setting_key) DO UPDATE SET value=excluded.value'),
        {'id': uuid4().hex, 'u': request.state.user_id.hex, 'k': 'current_organization', 'v': json.dumps(chosen)})
    request.state.audit_details = {'entity_type': 'core.work_context', 'entity_id': request.state.user_id.hex,
        'old': {'organization_id': old['selected_id']}, 'new': {'organization_id': chosen}}
    return await context(session, request)


async def validate_default(session, value):
    if value == '':
        return
    if not await session.scalar(text('SELECT 1 FROM organizations WHERE id=:i AND is_active=1'), {'i': uid(value)}):
        raise HTTPException(422, 'Default organization must be active')
