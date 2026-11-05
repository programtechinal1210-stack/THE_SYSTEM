"""Transfer legs run inside the existing posting transaction and writer lock."""
from decimal import Decimal, localcontext, ROUND_HALF_UP
from uuid import uuid4
from fastapi import HTTPException
from .inventory_service import InventoryService
from .posting_access import warehouse
from .reservation_service import ReservationService
from ..domain.financial_policy import quantity, money, COST_SCALE, transfer_allocation
from ..infrastructure.posting_repository import PostingRepository


class TransferPosting:
    def __init__(self, session, request):
        self.session, self.request = session, request
        self.repo = PostingRepository(session)

    async def apply(self, doc, lines, entity, at):
        dest = doc.get('destination_warehouse_id')
        if not dest or dest == doc['warehouse_id']:
            raise HTTPException(422, 'DISTINCT_TRANSFER_WAREHOUSES_REQUIRED')
        target = await warehouse(self.session, self.request, dest, 'inventory.documents.post')
        owner = await self.repo.one('SELECT * FROM inv_warehouse_owners WHERE warehouse_id=:w', w=dest)
        if target['organization_id'] != doc['organization_id'] or not owner or owner['legal_entity_id'] != entity['id']:
            raise HTTPException(409, 'TRANSFER_OWNER_SCOPE_MISMATCH')
        service = InventoryService(self.session, self.request)
        for line in lines:
            item = await service._reference('inv_items', line['item_id'])
            if item['organization_id'] != doc['organization_id'] or item['tracking_policy'] != 'none':
                raise HTTPException(422, 'TRANSFER_ITEM_INELIGIBLE')
            unit = await service._reference('inv_units', item['base_unit_id'])
            q = quantity(line['base_quantity'], unit['precision'])
            for field, wh in [('location_id', doc['warehouse_id']), ('destination_location_id', dest)]:
                if line[field]:
                    loc = await service._reference('inv_locations', line[field])
                    if loc['warehouse_id'] != wh:
                        raise HTTPException(422, 'TRANSFER_LOCATION_MISMATCH')
            if line.get('request_line_id') or doc.get('source_module'):
                raise HTTPException(422, 'TRANSFER_CONSUMPTION_LINK_FORBIDDEN')
            valuation = await self.repo.one('SELECT * FROM inv_valuation_state WHERE legal_entity_id=:l AND item_id=:i AND valuation_currency_id=:c',
                l=entity['id'], i=item['id'], c=entity['valuation_currency_id'])
            if not valuation or Decimal(valuation['quantity_total']) <= 0:
                raise HTTPException(409, 'INSUFFICIENT_STOCK')
            average = Decimal(valuation['avg_cost'])
            receipt = doc['document_type'] == 'TRANSFER_RECEIPT'
            source_status = 'IN_TRANSIT' if receipt else 'AVAILABLE'
            source = await self.balance(doc, entity, item['id'], doc['warehouse_id'], line['location_id'], source_status)
            on_hand = Decimal(source['quantity_on_hand']) if source else Decimal(0)
            if q > on_hand:
                raise HTTPException(409, 'INSUFFICIENT_STOCK')
            if receipt:
                original = await self.repo.one('SELECT l.*,d.status,d.document_type,d.organization_id,d.legal_entity_id,d.warehouse_id,d.destination_warehouse_id '
                    'FROM inv_document_lines l JOIN inv_effective_documents d ON d.id=l.document_id WHERE l.id=:i', i=line['dispatch_line_id'])
                if not original or original['status'] not in ('POSTED','CLOSED') or original['document_type'] != 'TRANSFER_DISPATCH':
                    raise HTTPException(409, 'POSTED_DISPATCH_REQUIRED')
                if any(original[k] != doc[k] for k in ('organization_id','warehouse_id','destination_warehouse_id')) or original['legal_entity_id'] != entity['id'] or any(original[k] != line[k] for k in ('item_id','location_id','destination_location_id')):
                    raise HTTPException(422, 'TRANSFER_DISPATCH_SCOPE_MISMATCH')
                previous = await self.repo.many("SELECT l.base_quantity,l.amount_valuation FROM inv_document_lines l JOIN inv_effective_documents d ON d.id=l.document_id WHERE l.dispatch_line_id=:i AND (d.status IN ('POSTED','CLOSED') OR (d.id=:current AND l.line_no<:number)) AND d.document_type IN ('TRANSFER_RECEIPT','LOSS_TRANSIT')", i=original['id'], current=doc['id'], number=line['line_no'])
                received = sum((Decimal(r['base_quantity']) for r in previous), Decimal(0))
                remaining = Decimal(original['base_quantity']) - received
                if q > remaining:
                    raise HTTPException(409, 'TRANSFER_OVER_RECEIPT')
                value = transfer_allocation(original['base_quantity'], original['amount_valuation'], received,
                    sum((Decimal(r['amount_valuation']) for r in previous), Decimal(0)), q)
            else:
                reserved = ReservationService.amount(await ReservationService(self.session, self.request).outstanding(doc['warehouse_id'], item['id'], line['location_id']))
                if q > on_hand - reserved:
                    raise HTTPException(409, 'INSUFFICIENT_UNRESERVED_STOCK')
                with localcontext() as ctx:
                    ctx.prec = 50
                    value = money(Decimal(valuation['inventory_value']) * q / Decimal(valuation['quantity_total']))
            with localcontext() as ctx:
                ctx.prec = 50
                cost = (value / q).quantize(COST_SCALE, rounding=ROUND_HALF_UP)
            await self.repo.update('inv_document_lines', line['id'], {'valuation_currency_id':entity['valuation_currency_id'],
                'unit_cost_valuation':str(cost), 'amount_valuation':str(value)})
            await self.leg(doc, line, entity, at, source, doc['warehouse_id'], line['location_id'], source_status, -q, -value, average, 'SOURCE')
            dispatch = doc['document_type'] == 'TRANSFER_DISPATCH'
            destination_wh = doc['warehouse_id'] if dispatch else dest
            destination_loc = line['location_id'] if dispatch else line['destination_location_id']
            destination_status = 'IN_TRANSIT' if dispatch else 'AVAILABLE'
            balance = await self.balance(doc, entity, item['id'], destination_wh, destination_loc, destination_status)
            await self.leg(doc, line, entity, at, balance, destination_wh, destination_loc, destination_status, q, value, average, 'DESTINATION')

    async def balance(self, doc, entity, item, wh, loc, status):
        return await self.repo.one("SELECT * FROM inv_stock_balances WHERE organization_id=:o AND legal_entity_id=:l AND warehouse_id=:w AND COALESCE(location_id,'')=:loc AND item_id=:i AND stock_status=:s",
            o=doc['organization_id'], l=entity['id'], w=wh, loc=loc or '', i=item, s=status)

    async def leg(self, doc, line, entity, at, balance, wh, loc, status, q, value, average, key, new_average=None):
        from .stocktake_service import check_freeze
        await check_freeze(self.session,wh,line['item_id'],loc,status,q,doc.get('stocktake_id'))
        before = Decimal(balance['quantity_on_hand']) if balance else Decimal(0)
        after = before + q
        if after < 0:
            raise HTTPException(409, 'INSUFFICIENT_STOCK')
        fields = {'organization_id':doc['organization_id'], 'legal_entity_id':entity['id'], 'warehouse_id':wh,
                  'location_id':loc, 'item_id':line['item_id'], 'stock_status':status}
        values = {'quantity_on_hand':str(after), 'version':balance['version'] + 1 if balance else 1}
        if balance:
            await self.repo.update('inv_stock_balances', balance['id'], values)
        else:
            await self.repo.insert('inv_stock_balances', {**fields, **values, 'id':uuid4().hex})
        await self.repo.insert('inv_stock_ledger', {**fields, 'id':uuid4().hex, 'document_line_id':line['id'],
            'posting_group_id':doc['id'], 'posting_leg_key':key, 'quantity_delta':str(q), 'value_delta_valuation':str(value),
            'valuation_currency_id':entity['valuation_currency_id'], 'prev_qty':str(before), 'new_qty':str(after),
            'prev_avg_cost':str(average), 'new_avg_cost':str(average if new_average is None else new_average), 'posted_at':at})
