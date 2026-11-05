"""Warehouse legal owner configuration; current user context is never an owner."""
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import text
from core.access import require
from core import legal_entities
from .inventory_service import InventoryService, now

class OwnershipService:
    def __init__(self, session, request):
        self.session, self.request = session, request

    async def readiness(self, warehouse_id):
        wh = await InventoryService(self.session, self.request)._owned('warehouses', warehouse_id)
        if not await legal_entities.installed(self.session):
            return {'warehouse_id': warehouse_id, 'ready': False, 'reason': 'SETUP_MIGRATION_REQUIRED'}
        row = (await self.session.execute(text('SELECT o.*,e.status,e.valuation_currency_id,c.code AS valuation_currency,'
            'c.is_active AS currency_active FROM inv_warehouse_owners o JOIN core_legal_entities e ON e.id=o.legal_entity_id '
            'LEFT JOIN core_currencies c ON c.id=e.valuation_currency_id WHERE o.warehouse_id=:w'), {'w': warehouse_id})).mappings().first()
        reasons = []
        if not row:
            reasons.append('LEGAL_OWNER_NOT_CONFIGURED')
        else:
            if row['status'] != 'approved':
                reasons.append('LEGAL_ENTITY_NOT_APPROVED')
            if not row['valuation_currency_id'] or not row['currency_active']:
                reasons.append('VALUATION_CURRENCY_NOT_READY')
        if wh['status'] != 'active':
            reasons.append('WAREHOUSE_NOT_ACTIVE')
        has_controls = await self.session.scalar(text("SELECT 1 FROM sqlite_master WHERE name='inv_financial_controls'"))
        enabled = await self.session.scalar(text('SELECT posting_enabled FROM inv_financial_controls WHERE legal_entity_id=:l'),
            {'l': row['legal_entity_id']}) if has_controls and row else False
        return {'warehouse_id': warehouse_id, 'ready': not reasons, 'financial_ready': not reasons and bool(enabled), 'reasons': reasons,
                'legal_entity_id': row['legal_entity_id'] if row else None,
                'valuation_currency': row['valuation_currency'] if row else None}

    async def assign(self, warehouse_id, legal_entity_id):
        legal_entities.manage(self.request)
        if not await legal_entities.installed(self.session):
            raise HTTPException(409, 'Legal reference migration has not been deployed')
        wh = await InventoryService(self.session, self.request)._owned('warehouses', warehouse_id, 'manage')
        entity = await legal_entities.row(self.session, legal_entity_id)
        if entity['status'] != 'approved':
            raise HTTPException(409, 'Approve the legal entity first')
        if not await self.session.scalar(text('SELECT 1 FROM core_legal_organization_links WHERE legal_entity_id=:l AND organization_id=:o'),
            {'l': entity['id'], 'o': wh['organization_id']}):
            raise HTTPException(409, 'Approve the legal entity to organization relationship first')
        old = (await self.session.execute(text('SELECT * FROM inv_warehouse_owners WHERE warehouse_id=:w'), {'w': warehouse_id})).mappings().first()
        if old and old['legal_entity_id'] != entity['id']:
            # Any ownership reassignment requires a separate approved migration.
            raise HTTPException(409, 'Existing warehouse legal ownership cannot be reassigned here')
        await self.session.execute(text('INSERT INTO inv_warehouse_owners(warehouse_id,legal_entity_id,organization_id,approved_by,approved_at) '
            'VALUES(:w,:l,:o,:by,:at) ON CONFLICT(warehouse_id) DO NOTHING'),
            {'w': warehouse_id, 'l': entity['id'], 'o': wh['organization_id'], 'by': self.request.state.user_id.hex, 'at': now()})
        self.request.state.audit_details = {'entity_type': 'inventory.warehouse_owner', 'entity_id': warehouse_id,
            'old': dict(old) if old else None, 'new': {'legal_entity_id': entity['id'], 'organization_id': wh['organization_id']}}
        return await self.readiness(warehouse_id)
