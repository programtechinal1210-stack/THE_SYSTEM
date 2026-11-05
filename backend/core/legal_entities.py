"""Core legal reference ownership; independent of inventory and PM business code."""
from datetime import datetime, timezone
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from core.access import require
from core.work_context import uid, organization_allowed


def now():
    return datetime.now(timezone.utc).isoformat()


async def installed(session):
    return bool(await session.scalar(text("SELECT 1 FROM sqlite_master WHERE type='table' AND name='core_legal_entities'")))


def manage(request):
    require(request, 'core.legal_entities.manage')
    if not request.state.is_admin and 'institution' not in request.state.permission_global_scopes.get('core.legal_entities.manage', set()):
        raise HTTPException(403, 'Legal entity configuration requires institution scope')


async def row(session, identifier):
    if not await installed(session):
        raise HTTPException(409, 'Legal reference migration has not been deployed')
    result = (await session.execute(text('SELECT e.*,c.code AS valuation_currency FROM core_legal_entities e '
        'LEFT JOIN core_currencies c ON c.id=e.valuation_currency_id WHERE e.id=:i'), {'i': uid(identifier)})).mappings().first()
    if not result:
        raise HTTPException(404, 'Legal entity unavailable')
    return dict(result)


async def currency(session, code):
    if code is None:
        return None
    identifier = await session.scalar(text('SELECT id FROM core_currencies WHERE code=:c AND is_active=1'), {'c': code})
    if not identifier:
        raise HTTPException(422, 'Unknown or inactive central currency')
    return identifier


async def listing(session, request):
    require(request, 'core.legal_entities.view')
    if not await installed(session):
        return {'items': [], 'links': [], 'setup_required': True}
    rows = (await session.execute(text('SELECT e.*,c.code AS valuation_currency FROM core_legal_entities e '
        'LEFT JOIN core_currencies c ON c.id=e.valuation_currency_id ORDER BY e.code'))).mappings().all()
    links = [dict(r) for r in (await session.execute(text('SELECT * FROM core_legal_organization_links'))).mappings()]
    broad = request.state.is_admin or 'institution' in request.state.permission_global_scopes.get('core.legal_entities.view', set())
    permitted = {link['legal_entity_id'] for link in links if organization_allowed(request, 'core.legal_entities.view', link['organization_id'])}
    return {'items': [dict(r) for r in rows if broad or r['id'] in permitted],
            'links': [l for l in links if broad or organization_allowed(request, 'core.legal_entities.view', l['organization_id'])], 'setup_required': False}


async def create(session, request, data):
    manage(request)
    if not await installed(session):
        raise HTTPException(409, 'Legal reference migration has not been deployed')
    identifier = uuid4().hex
    values = {'id': identifier, 'code': data.code, 'name': data.name,
              'currency': await currency(session, data.valuation_currency), 'by': request.state.user_id.hex, 'at': now()}
    try:
        await session.execute(text('INSERT INTO core_legal_entities(id,code,name,valuation_currency_id,created_by,created_at) '
            'VALUES(:id,:code,:name,:currency,:by,:at)'), values)
    except IntegrityError:
        raise HTTPException(409, 'Legal entity business code already exists') from None
    result = await row(session, identifier)
    request.state.audit_details = {'entity_type': 'core.legal_entity', 'entity_id': identifier, 'new': result}
    return result


async def update(session, request, identifier, data):
    manage(request)
    old = await row(session, identifier)
    if data.code != old['code']:
        raise HTTPException(422, 'Legal entity business code is immutable')
    cid = await currency(session, data.valuation_currency)
    if old['valuation_locked'] and cid != old['valuation_currency_id']:
        raise HTTPException(409, 'Valuation currency is locked by posted movements')
    changed = cid != old['valuation_currency_id']
    await session.execute(text('UPDATE core_legal_entities SET name=:name,valuation_currency_id=:c,'
        'status=:s,approved_by=:by,approved_at=:at WHERE id=:i'),
        {'name': data.name, 'c': cid, 's': 'draft' if changed else old['status'],
         'by': None if changed else old['approved_by'], 'at': None if changed else old['approved_at'], 'i': old['id']})
    result = await row(session, identifier)
    request.state.audit_details = {'entity_type': 'core.legal_entity', 'entity_id': old['id'], 'old': old, 'new': result}
    return result


async def approve(session, request, identifier):
    manage(request)
    old = await row(session, identifier)
    if not old['valuation_currency']:
        raise HTTPException(409, 'Configure the legal valuation currency first')
    await currency(session, old['valuation_currency'])
    await session.execute(text("UPDATE core_legal_entities SET status='approved',approved_by=:u,approved_at=:at WHERE id=:i"),
                          {'u': request.state.user_id.hex, 'at': now(), 'i': old['id']})
    result = await row(session, identifier)
    request.state.audit_details = {'entity_type': 'core.legal_entity', 'entity_id': old['id'], 'old': old, 'new': result}
    return result


async def link(session, request, identifier, organization_id):
    manage(request)
    entity = await row(session, identifier)
    if entity['status'] != 'approved':
        raise HTTPException(409, 'Approve the legal entity first')
    org = uid(organization_id)
    if not await session.scalar(text('SELECT 1 FROM organizations WHERE id=:i AND is_active=1'), {'i': org}):
        raise HTTPException(422, 'Organization must be active')
    await session.execute(text('INSERT INTO core_legal_organization_links(legal_entity_id,organization_id,approved_by,approved_at) '
        'VALUES(:l,:o,:by,:at) ON CONFLICT(legal_entity_id,organization_id) DO NOTHING'),
        {'l': entity['id'], 'o': org, 'by': request.state.user_id.hex, 'at': now()})
    request.state.audit_details = {'entity_type': 'core.legal_entity_link', 'entity_id': entity['id'],
                                   'new': {'organization_id': org}}
    return {'legal_entity_id': entity['id'], 'organization_id': org}


async def lock_valuation(session, identifier):
    entity = await row(session, identifier)
    if entity['status'] != 'approved' or not entity['valuation_currency']:
        raise HTTPException(409, 'LEGAL_VALUATION_NOT_READY')
    await currency(session, entity['valuation_currency'])
    await session.execute(text('UPDATE core_legal_entities SET valuation_locked=1 WHERE id=:i'), {'i': entity['id']})
    return entity
