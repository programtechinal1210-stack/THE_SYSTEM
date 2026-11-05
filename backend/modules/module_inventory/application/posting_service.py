"""Atomic inventory posting; Core owns the single commit and audit insertion."""
import asyncio
import json
from decimal import Decimal, localcontext, ROUND_HALF_UP
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError
from core import legal_entities
from core.access import require
from .document_service import DocumentService
from .inventory_service import InventoryService, now
from ..domain.document_policy import DocumentState
from ..domain.financial_policy import Valuation, quantity, COST_SCALE
from ..integrations.currency_gateway import InventoryCurrencyGateway


class InventoryPostingService(DocumentService):
    async def post(self, identifier, key):
        require(self.request, 'inventory.documents.post')
        for attempt in range(3):
            try:
                return await self._post(identifier, key)
            except OperationalError as exc:
                if not any(s in str(exc).lower() for s in ('database is locked', 'database table is locked', 'sqlite_busy', 'sqlite_locked')):
                    raise
                await self.session.rollback()
                if attempt == 2:
                    raise HTTPException(503, 'WRITE_CONTENTION_RETRY', headers={'Retry-After': '1'}) from None
                await asyncio.sleep(.05 * (attempt + 1))

    async def _post(self, identifier, key):
        # A write statement acquires SQLite's writer before any stock/state reads.
        # Filtering posted rows allows idempotent replay without mutating history.
        await self.session.execute(text("UPDATE inv_documents SET updated_at=updated_at WHERE id=:i AND status NOT IN ('POSTED','CLOSED')"), {'i': identifier})
        doc = await self.raw(identifier, 'inventory.documents.post')
        state = DocumentState(doc['created_by'], doc['status'], doc['approved_by'], doc['posted_by'], doc['posting_key'])
        try:
            future = state.post(self.request.state.user_id.hex, key)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from None
        if doc['status'] in ('POSTED','CLOSED'):
            return {'id': identifier, 'status': doc['status'], 'posting_key': key, 'replayed': True}
        duplicate = await self.repo.one('SELECT id FROM inv_documents WHERE organization_id=:o AND posting_key=:k', o=doc['organization_id'], k=key)
        if duplicate:
            raise HTTPException(409, 'IDEMPOTENCY_KEY_REUSED')
        owner = await self.repo.one('SELECT * FROM inv_warehouse_owners WHERE warehouse_id=:w', w=doc['warehouse_id'])
        if not owner or owner['organization_id'] != doc['organization_id']:
            raise HTTPException(409, 'LEGAL_OWNER_NOT_CONFIGURED')
        entity = await legal_entities.row(self.session, owner['legal_entity_id'])
        if entity['status'] != 'approved' or not entity['valuation_currency_id']:
            raise HTTPException(409, 'LEGAL_VALUATION_NOT_READY')
        control = await self.repo.one('SELECT * FROM inv_financial_controls WHERE legal_entity_id=:l', l=entity['id'])
        if not control or not control['posting_enabled']:
            raise HTTPException(409, 'FINANCIAL_ACTIVATION_REQUIRED')
        if control['closed_through'] and doc['document_date'] <= control['closed_through']:
            raise HTTPException(409, 'FINANCIAL_PERIOD_CLOSED')
        await legal_entities.lock_valuation(self.session, entity['id'])
        lines = await self.repo.many('SELECT * FROM inv_document_lines WHERE document_id=:i ORDER BY line_no', i=identifier)
        if not lines:
            raise HTTPException(409, 'DOCUMENT_HAS_NO_LINES')
        if doc['document_type'] not in ('ISSUE_CUSTODY','CONSUMPTION','RETURN_INTERNAL','REVERSAL'):
            for line in lines:
                if await self.repo.one('SELECT location_id FROM inv_custody_accounts WHERE location_id IN (:s,:d)',s=line['location_id'],d=line['destination_location_id']):
                    raise HTTPException(409,'CUSTODY_LOCATION_REQUIRES_CUSTODY_OPERATION')
        if doc.get('source_module'):
            from core.module_registry import registry
            await registry.validate_source_reference(
                doc['source_module'], doc['source_type'], self.session,
                doc['organization_id'], doc['source_id'], doc['document_type'],
                doc['warehouse_id'], lines, require_posted=True,
            )
        service = InventoryService(self.session, self.request)
        at = now()
        if doc['document_type']=='REVERSAL':
            from .reversal_service import ReversalPosting
            try:
                await ReversalPosting(self.session,self.request).apply(doc,lines,entity,at)
            except ValueError as exc:
                raise HTTPException(409,str(exc)) from None
            lines=[]
        elif doc['document_type']=='ADJUSTMENT':
            if doc['adjustment_kind']=='COUNT':
                from .count_posting import CountPosting as AdjustmentPosting
            elif doc['adjustment_kind']=='VALUE':
                from .value_correction_service import ValueCorrectionPosting as AdjustmentPosting
            else:raise HTTPException(409,'UNKNOWN_ADJUSTMENT_KIND')
            try:
                await AdjustmentPosting(self.session,self.request).apply(doc,lines,entity,at)
            except ValueError as exc:
                raise HTTPException(409,str(exc)) from None
            lines=[]
        elif doc['document_type']=='RETURN_SUPPLIER':
            from .supplier_return_service import SupplierReturnPosting
            try:
                await SupplierReturnPosting(self.session,self.request).apply(doc,lines,entity,at)
            except ValueError as exc:
                raise HTTPException(409,str(exc)) from None
            lines=[]
        elif doc['document_type'] in ('STATUS_CHANGE','SCRAP'):
            from .status_service import StatusPosting
            try:
                await StatusPosting(self.session,self.request).apply(doc,lines,entity,at)
            except ValueError as exc:
                raise HTTPException(409,str(exc)) from None
            lines=[]
        elif doc['document_type'] in ('ISSUE_CUSTODY','CONSUMPTION','RETURN_INTERNAL'):
            from .custody_service import CustodyPosting
            try:
                await CustodyPosting(self.session,self.request).apply(doc,lines,entity,at)
            except ValueError as exc:
                raise HTTPException(409,str(exc)) from None
            lines=[]
        elif doc['document_type']=='LOSS_TRANSIT':
            from .transit_loss_service import TransitLossPosting
            try:
                await TransitLossPosting(self.session,self.request).apply(doc,lines,entity,at)
            except ValueError as exc:
                raise HTTPException(409,str(exc)) from None
            lines=[]
        elif doc['document_type'].startswith('TRANSFER_'):
            from .transfer_service import TransferPosting
            try:
                await TransferPosting(self.session, self.request).apply(doc, lines, entity, at)
            except ValueError as exc:
                raise HTTPException(409,str(exc)) from None
            lines = []
        for line in lines:
            from .stocktake_service import check_freeze
            await check_freeze(self.session,doc['warehouse_id'],line['item_id'],line['location_id'],'AVAILABLE',line['base_quantity'])
            item = await service._reference('inv_items', line['item_id'])
            if item['organization_id'] != doc['organization_id'] or item['tracking_policy'] != 'none':
                raise HTTPException(422, 'Item is not eligible for posting')
            base_unit = await service._reference('inv_units', item['base_unit_id'])
            q = quantity(line['base_quantity'], base_unit['precision'])
            if line['location_id']:
                loc = await service._reference('inv_locations', line['location_id'])
                if loc['warehouse_id'] != doc['warehouse_id']:
                    raise HTTPException(422, 'Location is not in the document warehouse')
            balance = await self.repo.one('SELECT * FROM inv_stock_balances WHERE legal_entity_id=:l AND warehouse_id=:w '
                "AND COALESCE(location_id,'')=:loc AND item_id=:i AND stock_status='AVAILABLE'",
                l=entity['id'], w=doc['warehouse_id'], loc=line['location_id'] or '', i=item['id'])
            before_q = Decimal(balance['quantity_on_hand']) if balance else Decimal(0)
            valuation = await self.repo.one('SELECT * FROM inv_valuation_state WHERE legal_entity_id=:l AND item_id=:i AND valuation_currency_id=:c',
                l=entity['id'], i=item['id'], c=entity['valuation_currency_id'])
            before = Valuation(Decimal(valuation['quantity_total']), Decimal(valuation['inventory_value']), Decimal(valuation['avg_cost'])) if valuation else Valuation.empty()
            try:
                if doc['document_type'] == 'RECEIPT':
                    source = await self.session.scalar(text('SELECT code FROM core_currencies WHERE id=:i AND is_active=1'), {'i': line['transaction_currency_id']})
                    snap = await InventoryCurrencyGateway(self.session).receipt_snapshot(line['quantity'], line['original_unit_price'], source,
                        entity['valuation_currency'], doc['document_date'])
                    value = Decimal(snap['amount_valuation'])
                    after = before.receive(q, value)
                    delta_q, delta_v = q, value
                    with localcontext() as ctx:
                        ctx.prec = 50
                        unit_cost = (value / q).quantize(COST_SCALE, rounding=ROUND_HALF_UP)
                    financial = {'original_amount': snap['original_amount'], 'fx_rate': snap['fx_rate'],
                        'fx_effective_at': json.dumps(snap['fx_effective_dates']),
                        'fx_source_ref': json.dumps(snap['fx_source_ref'], default=str),
                        'valuation_currency_id': entity['valuation_currency_id'],
                        'unit_cost_valuation': str(unit_cost), 'amount_valuation': str(value)}
                else:
                    if before_q < q:
                        raise ValueError('INSUFFICIENT_STOCK')
                    from .reservation_service import ReservationService
                    await ReservationService(self.session,self.request).consume(doc,line,q,before_q)
                    after, value = before.issue(q)
                    delta_q, delta_v = -q, -value
                    with localcontext() as ctx:
                        ctx.prec = 50
                        unit_cost = (value / q).quantize(COST_SCALE, rounding=ROUND_HALF_UP)
                    financial = {'valuation_currency_id': entity['valuation_currency_id'],
                                 'unit_cost_valuation': str(unit_cost), 'amount_valuation': str(value)}
            except ValueError as exc:
                raise HTTPException(409, str(exc)) from None
            after_q = before_q + delta_q
            if after_q < 0:
                raise HTTPException(409, 'INSUFFICIENT_STOCK')
            await self.repo.update('inv_document_lines', line['id'], financial)
            balance_values = {'quantity_on_hand': str(after_q), 'version': balance['version'] + 1 if balance else 1}
            if balance:
                await self.repo.update('inv_stock_balances', balance['id'], balance_values)
            else:
                await self.repo.insert('inv_stock_balances', {**balance_values, 'id': uuid4().hex,
                    'organization_id': doc['organization_id'], 'legal_entity_id': entity['id'],
                    'warehouse_id': doc['warehouse_id'], 'location_id': line['location_id'], 'item_id': item['id']})
            valuation_values = {'quantity_total': str(after.quantity_total), 'inventory_value': str(after.inventory_value),
                                'avg_cost': str(after.avg_cost), 'version': valuation['version'] + 1 if valuation else 1}
            if valuation:
                await self.repo.update('inv_valuation_state', valuation['id'], valuation_values)
            else:
                await self.repo.insert('inv_valuation_state', {**valuation_values, 'id': uuid4().hex,
                    'legal_entity_id': entity['id'], 'item_id': item['id'], 'valuation_currency_id': entity['valuation_currency_id']})
            await self.repo.insert('inv_stock_ledger', {'id': uuid4().hex, 'document_line_id': line['id'],
                'posting_group_id': identifier, 'organization_id': doc['organization_id'], 'legal_entity_id': entity['id'],
                'warehouse_id': doc['warehouse_id'], 'location_id': line['location_id'], 'item_id': item['id'],
                'quantity_delta': str(delta_q), 'value_delta_valuation': str(delta_v),
                'valuation_currency_id': entity['valuation_currency_id'], 'prev_qty': str(before_q), 'new_qty': str(after_q),
                'prev_avg_cost': str(before.avg_cost), 'new_avg_cost': str(after.avg_cost), 'posted_at': at})
        await self.repo.update('inv_documents', identifier, {'status': future.status, 'legal_entity_id': entity['id'],
            'posted_by': self.request.state.user_id.hex, 'posted_at': at, 'posting_key': key, 'updated_at': at})
        event = {'event_id': uuid4().hex, 'document_id': identifier, 'organization_id': doc['organization_id'],
                 'legal_entity_id': entity['id'], 'actor_id': self.request.state.user_id.hex, 'occurred_at': at, 'schema_version': 1}
        await self.repo.insert('inv_outbox_events', {'id': event['event_id'], 'organization_id': doc['organization_id'],
            'document_id': identifier, 'event_name': 'inventory.' + doc['document_type'].lower() + '.posted',
            'payload': json.dumps(event), 'created_at': at})
        self.request.state.audit_details = {'entity_type': 'inventory.document', 'entity_id': identifier,
            'old': doc, 'new': {'status': 'POSTED', 'posted_by': self.request.state.user_id.hex, 'posting_key': key}}
        return {'id': identifier, 'status': 'POSTED', 'posting_key': key, 'event_id': event['event_id'], 'integration_delivery_status': 'PENDING'}
