from collections import defaultdict
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy import text
from core import legal_entities
from core.access import require
from .inventory_service import now
from .posting_access import warehouse, costs
from ..infrastructure.posting_repository import PostingRepository


class StockService:
    def __init__(self, session, request):
        self.session, self.request = session, request
        self.repo = PostingRepository(session)

    async def balances(self, warehouse_id):
        await warehouse(self.session, self.request, warehouse_id, 'inventory.stock.view')
        rows = await self.repo.many('SELECT * FROM inv_stock_balances WHERE warehouse_id=:w ORDER BY item_id,id', w=warehouse_id)
        from .reservation_service import ReservationService
        reservations=ReservationService(self.session,self.request)
        active=await self.repo.many("SELECT * FROM inv_reservations WHERE warehouse_id=:w AND status='ACTIVE' "
            "AND (expires_at IS NULL OR expires_at>:at)",w=warehouse_id,at=now())
        grouped=defaultdict(list)
        for reservation in active:
            grouped[(reservation['item_id'],reservation['location_id'])].append(reservation)
        result=[]
        for row in rows:
            reserved=reservations.amount(grouped[(row['item_id'],row['location_id'])]) if row['stock_status']=='AVAILABLE' else Decimal(0)
            on_hand=Decimal(row['quantity_on_hand'])
            eligible=on_hand if row['stock_status']=='AVAILABLE' else Decimal(0)
            raw=eligible-reserved
            result.append({**row,'on_hand':str(on_hand),'eligible_on_hand':str(eligible),'active_reserved':str(reserved),
                'raw_available':str(raw),'available_to_issue':str(max(Decimal(0),raw)),
                'reservation_deficit':str(max(Decimal(0),-raw)),
                'reservation_status':'INCONSISTENT_RESERVATION' if raw<0 else 'CONSISTENT'})
        return {'items':result,'reservation_workflow':'ENABLED'}

    async def movements(self, warehouse_id, skip=0, limit=50):
        wh = await warehouse(self.session, self.request, warehouse_id, 'inventory.stock.view')
        rows = await self.repo.many('SELECT * FROM inv_stock_ledger WHERE warehouse_id=:w ORDER BY ledger_seq DESC LIMIT :l OFFSET :s',
                                   w=warehouse_id, l=limit, s=skip)
        if not costs(self.request, wh['organization_id']):
            financial = {'value_delta_valuation','valuation_currency_id','prev_avg_cost','new_avg_cost'}
            rows = [{k:v for k,v in r.items() if k not in financial} for r in rows]
        return {'items': rows}

    async def controls(self, identifier, payload):
        legal_entities.manage(self.request)
        require(self.request, 'inventory.finance.configure')
        entity = await legal_entities.row(self.session, identifier)
        if entity['status'] != 'approved':
            raise HTTPException(409, 'Approve legal entity and currency first')
        old = await self.repo.one('SELECT * FROM inv_financial_controls WHERE legal_entity_id=:i', i=identifier)
        through = payload.closed_through.isoformat() if payload.closed_through else None
        if old and old['closed_through'] and (not through or through < old['closed_through']):
            raise HTTPException(409, 'A closed period cannot be reopened by ordinary settings')
        await self.session.execute(text('INSERT INTO inv_financial_controls(legal_entity_id,posting_enabled,closed_through,updated_by,updated_at) '
            'VALUES(:i,:enabled,:date,:by,:at) ON CONFLICT(legal_entity_id) DO UPDATE SET posting_enabled=excluded.posting_enabled,'
            'closed_through=excluded.closed_through,updated_by=excluded.updated_by,updated_at=excluded.updated_at'),
            {'i': identifier, 'enabled': int(payload.posting_enabled), 'date': through, 'by': self.request.state.user_id.hex, 'at': now()})
        self.request.state.audit_details = {'entity_type': 'inventory.financial_controls', 'entity_id': identifier,
            'old': old, 'new': {'posting_enabled': payload.posting_enabled, 'closed_through': through}}
        return {'legal_entity_id': identifier, 'posting_enabled': payload.posting_enabled, 'closed_through': through}

    async def reconciliation(self, warehouse_id):
        await warehouse(self.session, self.request, warehouse_id, 'inventory.reports.view')
        ledgers = await self.repo.many('SELECT * FROM inv_stock_ledger WHERE warehouse_id=:w', w=warehouse_id)
        balances = await self.repo.many('SELECT * FROM inv_stock_balances WHERE warehouse_id=:w', w=warehouse_id)
        total = defaultdict(Decimal)
        key = lambda r: (r['legal_entity_id'], r['item_id'], r['location_id'] or '', r['stock_status'])
        for r in ledgers:
            total[key(r)] += Decimal(r['quantity_delta'])
        discrepancies = []
        for r in balances:
            expected = total.pop(key(r), Decimal(0))
            if expected != Decimal(r['quantity_on_hand']):
                discrepancies.append({'balance_id': r['id'], 'quantity_difference': str(Decimal(r['quantity_on_hand']) - expected)})
        discrepancies += [{'missing_balance': list(k), 'quantity_difference': str(-v)} for k,v in total.items() if v]
        value_differences = None
        global_costs = self.request.state.is_admin or 'institution' in self.request.state.permission_global_scopes.get('inventory.costs.view', set())
        global_reports = self.request.state.is_admin or 'institution' in self.request.state.permission_global_scopes.get('inventory.reports.view', set())
        if global_costs and global_reports:
            value_differences = []
            scopes = {(r['legal_entity_id'], r['item_id'], r['valuation_currency_id']) for r in ledgers}
            for owner, item, currency in scopes:
                entries = await self.repo.many('SELECT quantity_delta,value_delta_valuation FROM inv_stock_ledger WHERE legal_entity_id=:o AND item_id=:i AND valuation_currency_id=:c', o=owner, i=item, c=currency)
                state = await self.repo.one('SELECT * FROM inv_valuation_state WHERE legal_entity_id=:o AND item_id=:i AND valuation_currency_id=:c', o=owner, i=item, c=currency)
                q = sum((Decimal(e['quantity_delta']) for e in entries), Decimal(0))
                v = sum((Decimal(e['value_delta_valuation']) for e in entries), Decimal(0))
                if not state or q != Decimal(state['quantity_total']) or v != Decimal(state['inventory_value']):
                    value_differences.append({'legal_entity_id': owner, 'item_id': item, 'reason': 'VALUATION_MISMATCH'})
        return {'quantity_differences': discrepancies, 'value_differences': value_differences,
                'quantity_match': not discrepancies, 'value_match': not value_differences if value_differences is not None else None}
