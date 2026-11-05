import json
from decimal import Decimal, localcontext
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from core.access import require
from .inventory_service import InventoryService, now
from .posting_access import warehouse, costs
from ..domain.financial_policy import quantity, decimal
from ..domain.document_policy import DocumentState
from ..infrastructure.posting_repository import PostingRepository

FINANCIAL = {'transaction_currency_id','original_unit_price','original_amount','valuation_currency_id',
             'fx_rate','fx_effective_at','fx_source_ref','unit_cost_valuation','amount_valuation','value_adjustment_amount','count_cost_basis','adjustment_cost_reason','count_proposal_currency'}


class DocumentService:
    def __init__(self, session, request):
        self.session, self.request = session, request
        self.repo = PostingRepository(session)

    async def raw(self, identifier, permission):
        require(self.request, permission)
        row = await self.repo.one('SELECT * FROM inv_documents WHERE id=:i', i=identifier)
        if not row:
            raise HTTPException(404, 'Document unavailable')
        await warehouse(self.session, self.request, row['warehouse_id'], permission)
        if row.get('destination_warehouse_id'):
            await warehouse(self.session, self.request, row['destination_warehouse_id'], permission)
        if row.get('adjustment_kind')=='COUNT' and permission=='inventory.documents.view':
            from .count_posting import CountPosting
            await CountPosting(self.session,self.request).authorize_document_sources(row,financial=False)
        if row['document_type']=='REVERSAL' and permission=='inventory.documents.view':
            source=await self.repo.one('SELECT * FROM inv_documents WHERE id=:i',i=row['reverses_document_id'])
            if source and source.get('adjustment_kind')=='COUNT':
                from .count_posting import CountPosting
                await CountPosting(self.session,self.request).authorize_document_sources(source,financial=False)
        if row['document_type']=='ADJUSTMENT' and permission!='inventory.documents.view':
            if row['adjustment_kind']=='COUNT':
                from .count_posting import CountPosting
                await CountPosting(self.session,self.request).authorize_document_sources(row)
            else:
                from .value_correction_service import ValueCorrectionPosting
                await ValueCorrectionPosting(self.session,self.request).authorize_document_sources(row)
        if row['document_type']=='REVERSAL' and permission!='inventory.documents.view':
            from .reversal_service import ReversalPosting
            await ReversalPosting(self.session,self.request).original(row['reverses_document_id'])
        return row

    async def detail(self, identifier):
        row = await self.raw(identifier, 'inventory.documents.view')
        for field in ('decision','closed'):
            if row.get(field+'_by'):
                actor=await self.repo.one('SELECT full_name FROM users WHERE id=:i',i=row[field+'_by'])
                row[field+'_actor_name']=actor['full_name'] if actor else ''
        if row.get('beneficiary_user_id'):
            holder=await self.repo.one('SELECT full_name FROM users WHERE id=:i',i=row['beneficiary_user_id'])
            row['beneficiary_name']=holder['full_name'] if holder else ''
        row['lines'] = await self.repo.many('SELECT * FROM inv_document_lines WHERE document_id=:i ORDER BY line_no', i=identifier)
        if row.get('stocktake_id'):
            source=await self.repo.one('SELECT count_no FROM inv_stocktakes WHERE id=:i AND warehouse_id=:w AND organization_id=:o',i=row['stocktake_id'],w=row['warehouse_id'],o=row['organization_id'])
            row['stocktake_no']=source['count_no'] if source else ''
            row['lines']=await self.repo.many('SELECT l.*,c.approved_difference AS count_difference,c.stock_status AS count_stock_status,cur.code AS count_proposal_currency FROM inv_document_lines l JOIN inv_stocktake_lines c ON c.id=l.stocktake_line_id AND c.stocktake_id=:s LEFT JOIN core_currencies cur ON cur.id=l.transaction_currency_id WHERE l.document_id=:i ORDER BY l.line_no',i=identifier,s=row['stocktake_id'])
        reversal=await self.repo.one("SELECT id,document_no FROM inv_documents WHERE reverses_document_id=:i AND status IN ('POSTED','CLOSED')",i=identifier)
        row['posted_reversal']=reversal
        if row.get('reverses_document_id'):
            original=await self.repo.one('SELECT document_no FROM inv_documents WHERE id=:i',i=row['reverses_document_id'])
            row['reversal_original_document_no']=original['document_no'] if original else ''
            row['reversal_legs']=await self.repo.many('SELECT warehouse_id,location_id,item_id,stock_status,quantity_delta,value_delta_valuation FROM inv_stock_ledger WHERE posting_group_id=:i ORDER BY ledger_seq',i=identifier if row['status'] in ('POSTED','CLOSED') else row['reverses_document_id'])
            if row['status'] not in ('POSTED','CLOSED'):
                for leg in row['reversal_legs']:
                    leg['quantity_delta']=str(-Decimal(leg['quantity_delta']));leg['value_delta_valuation']=str(-Decimal(leg['value_delta_valuation']))
            if not costs(self.request,row['organization_id']):
                for leg in row['reversal_legs']:leg.pop('value_delta_valuation')
        if row['document_type']=='RETURN_SUPPLIER' or row.get('adjustment_kind')=='VALUE':
            row['lines']=await self.repo.many("SELECT l.*,d.id AS origin_document_id,d.document_no AS origin_document_no,d.destination_warehouse_id AS _origin_destination FROM inv_document_lines l "
                "LEFT JOIN inv_document_lines original ON original.id=l.origin_line_id "
                "LEFT JOIN inv_documents d ON d.id=original.document_id AND d.organization_id=:o AND d.warehouse_id=:w "
                "AND d.document_type IN ('RECEIPT','TRANSFER_DISPATCH') AND d.status IN ('POSTED','CLOSED') WHERE l.document_id=:i ORDER BY l.line_no",i=identifier,o=row['organization_id'],w=row['warehouse_id'])
            destinations={}
            for line in row['lines']:
                destination=line.pop('_origin_destination')
                if destination:
                    if destination not in destinations:
                        try:
                            await warehouse(self.session,self.request,destination,'inventory.documents.view')
                            destinations[destination]=True
                        except HTTPException as exc:
                            if exc.status_code not in (403,404,409):raise
                            destinations[destination]=False
                    if not destinations[destination]:
                        line.pop('origin_document_id',None);line.pop('origin_document_no',None)
                        line['origin_reference_hidden']=True
        if not costs(self.request, row['organization_id']):
            row['lines'] = [{k:v for k,v in line.items() if k not in FINANCIAL} for line in row['lines']]
        return row

    async def lines(self, payload):
        service = InventoryService(self.session, self.request)
        result = []
        for number, line in enumerate(payload.lines, 1):
            item = await service._reference('inv_items', line.item_id.hex)
            if item['organization_id'] != payload.organization_id.hex or item['tracking_policy'] != 'none' or not item['base_unit_id']:
                raise HTTPException(422, 'Item scope, tracking or base unit is not eligible')
            unit = await service._reference('inv_units', item['base_unit_id'])
            input_unit = line.unit_id.hex if line.unit_id else item['base_unit_id']
            if input_unit == item['base_unit_id']:
                factor = Decimal(1)
                input_precision = unit['precision']
            else:
                alternative = await service._reference('inv_units', input_unit)
                input_precision = alternative['precision']
                if alternative['dimension'] != unit['dimension']:
                    raise HTTPException(422, 'Unit dimensions differ')
                conversion = await self.repo.one('SELECT * FROM inv_item_units WHERE item_id=:i AND unit_id=:u', i=item['id'], u=input_unit)
                if not conversion:
                    raise HTTPException(422, 'Item conversion is not configured')
                with localcontext() as ctx:
                    ctx.prec = 50
                    factor = decimal(conversion['factor_num'], positive=True) / decimal(conversion['factor_den'], positive=True)
            with localcontext() as ctx:
                ctx.prec = 50
                base = Decimal(0) if payload.document_type=='ADJUSTMENT' else quantity(quantity(line.quantity, input_precision) * factor, unit['precision'])
            loc = line.location_id.hex if line.location_id else None
            if loc:
                location = await service._reference('inv_locations', loc)
                if location['warehouse_id'] != payload.warehouse_id.hex:
                    raise HTTPException(422, 'Location belongs to a different warehouse')
            destination_location = line.destination_location_id.hex if line.destination_location_id else None
            if destination_location:
                destination = await service._reference('inv_locations', destination_location)
                expected_destination=payload.destination_warehouse_id.hex if payload.destination_warehouse_id else payload.warehouse_id.hex
                if destination['warehouse_id'] != expected_destination:
                    raise HTTPException(422, 'Destination location belongs to a different warehouse')
            if payload.document_type not in ('ISSUE_CUSTODY','CONSUMPTION','RETURN_INTERNAL'):
                custody_location=await self.repo.one('SELECT location_id FROM inv_custody_accounts WHERE location_id IN (:s,:d)',s=loc,d=destination_location)
                if custody_location:
                    raise HTTPException(422,'CUSTODY_LOCATION_REQUIRES_CUSTODY_OPERATION')
            currency_id = None
            if payload.document_type=='RETURN_SUPPLIER':
                from .supplier_return_service import SupplierReturnPosting
                await SupplierReturnPosting(self.session,self.request).origin(payload.organization_id.hex,payload.warehouse_id.hex,item['id'],line.origin_line_id.hex)
            if payload.document_type=='ADJUSTMENT':
                from .value_correction_service import ValueCorrectionPosting
                await ValueCorrectionPosting(self.session,self.request).origin(payload.organization_id.hex,payload.warehouse_id.hex,item['id'],line.origin_line_id.hex)
            if line.request_line_id:
                if payload.document_type == 'RECEIPT':
                    raise HTTPException(422,'REQUEST_SOURCE_REQUIRES_ISSUE')
                from .reservation_service import ReservationService
                source = await ReservationService(self.session,self.request).line(line.request_line_id.hex)
                if source['organization_id'] != payload.organization_id.hex or source['item_id'] != item['id']:
                    raise HTTPException(422,'REQUEST_ISSUE_SCOPE_MISMATCH')
                if source['request_status'] not in ('APPROVED','PARTIAL'):
                    raise HTTPException(409,'APPROVED_REQUEST_REQUIRED')
            if payload.document_type == 'RECEIPT':
                if not line.transaction_currency or line.original_unit_price is None:
                    raise HTTPException(422, 'Receipt currency and price are required')
                currency_id = await self.session.scalar(text('SELECT id FROM core_currencies WHERE code=:c AND is_active=1'), {'c': line.transaction_currency})
                if not currency_id:
                    raise HTTPException(422, 'Unknown or inactive transaction currency')
            elif line.original_unit_price is not None or line.transaction_currency is not None:
                raise HTTPException(422, 'Issue cost is determined by the server')
            result.append({'id': uuid4().hex, 'line_no': number, 'item_id': item['id'], 'unit_id': input_unit,
                'location_id': loc, 'quantity': line.quantity, 'base_quantity': str(base),
                'request_line_id': line.request_line_id.hex if line.request_line_id else None,
                'destination_location_id': destination_location,
                'dispatch_line_id': line.dispatch_line_id.hex if line.dispatch_line_id else None,
                'origin_line_id':line.origin_line_id.hex if line.origin_line_id else None,
                'value_adjustment_amount':line.value_adjustment_amount,
                'transaction_currency_id': currency_id, 'original_unit_price': line.original_unit_price})
        return result

    async def save(self, payload, identifier=None):
        code = 'inventory.documents.create'
        require(self.request, code)
        if identifier:
            await self.session.execute(text("UPDATE inv_documents SET updated_at=updated_at WHERE id=:i AND status='DRAFT'"), {'i': identifier})
        wh = await warehouse(self.session, self.request, payload.warehouse_id.hex, code)
        if wh['organization_id'] != payload.organization_id.hex:
            raise HTTPException(422, 'Document and warehouse organization differ')
        if payload.document_type=='ADJUSTMENT':
            from .value_correction_service import authorize
            authorize(self.request,payload.organization_id.hex)
        if payload.beneficiary_user_id:
            from .custody_service import CustodyPosting
            await CustodyPosting(self.session,self.request).validate_holder(payload.document_type,payload.beneficiary_user_id.hex,wh)
        if payload.destination_warehouse_id:
            destination = await warehouse(self.session, self.request, payload.destination_warehouse_id.hex, code)
            if destination['organization_id'] != payload.organization_id.hex:
                raise HTTPException(422, 'Transfer organizations differ')
        existing = await self.raw(identifier, code) if identifier else None
        if existing and (existing['document_type']=='REVERSAL' or existing.get('adjustment_kind')=='COUNT'):
            raise HTTPException(409,'GENERATED_DOCUMENT_ECONOMICS_IMMUTABLE')
        if existing and (existing['status'] != 'DRAFT' or existing['created_by'] != self.request.state.user_id.hex):
            raise HTTPException(409, 'Only the creator may edit a draft')
        if existing and existing['organization_id'] != payload.organization_id.hex:
            raise HTTPException(422, 'Document organization is immutable')
        source_reference = (
            payload.source_module,
            payload.source_type,
            payload.source_id.hex if payload.source_id else None,
        )
        if existing and source_reference != (
            existing.get('source_module'), existing.get('source_type'), existing.get('source_id')
        ):
            raise HTTPException(409, 'Document source reference is immutable')
        try:
            prepared = await self.lines(payload)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        if payload.source_module:
            from core.module_registry import registry
            await registry.validate_source_reference(
                payload.source_module, payload.source_type, self.session,
                payload.organization_id.hex, payload.source_id.hex,
                payload.document_type, payload.warehouse_id.hex, prepared,
            )
        identifier = identifier or uuid4().hex
        values = {'organization_id': payload.organization_id.hex, 'warehouse_id': payload.warehouse_id.hex,
            'reason':payload.reason,
            'beneficiary_user_id':payload.beneficiary_user_id.hex if payload.beneficiary_user_id else None,
            'custody_due_date':payload.custody_due_date.isoformat() if payload.custody_due_date else None,
            'source_stock_status':payload.source_stock_status,'target_stock_status':payload.target_stock_status,
            'counterparty_reference':payload.counterparty_reference,
            'adjustment_kind':payload.adjustment_kind,
            'destination_warehouse_id': payload.destination_warehouse_id.hex if payload.destination_warehouse_id else None,
            'document_type': payload.document_type, 'document_date': payload.document_date.isoformat(),
            'source_module': payload.source_module, 'source_type': payload.source_type,
            'source_id': payload.source_id.hex if payload.source_id else None,
            'document_no': payload.document_no or (existing['document_no'] if existing else payload.document_type[:3] + '-' + identifier[:16]),
            'updated_at': now()}
        try:
            if existing:
                await self.repo.update('inv_documents', identifier, values)
                await self.session.execute(text('DELETE FROM inv_document_lines WHERE document_id=:i'), {'i': identifier})
            else:
                await self.repo.insert('inv_documents', {**values, 'id': identifier, 'created_by': self.request.state.user_id.hex, 'created_at': now()})
            for line in prepared:
                await self.repo.insert('inv_document_lines', {**line, 'document_id': identifier})
        except IntegrityError:
            raise HTTPException(409, 'Document number or reference conflicts') from None
        self.request.state.audit_details = {'entity_type': 'inventory.document', 'entity_id': identifier,
            'old': existing, 'new': {'document_type': payload.document_type, 'line_count': len(prepared), 'status': 'DRAFT'}}
        # Creation permissions do not implicitly grant read/cost permissions.
        return {'id': identifier, 'status': 'DRAFT', 'document_no': values['document_no']}

    async def transition(self, identifier, action):
        permission = 'inventory.documents.approve' if action == 'approve' else 'inventory.documents.create'
        # Serialize state transitions before checking the current status.
        await self.session.execute(text("UPDATE inv_documents SET updated_at=updated_at WHERE id=:i AND status NOT IN ('POSTED','CLOSED')"), {'i': identifier})
        row = await self.raw(identifier, permission)
        state = DocumentState(row['created_by'], row['status'], row['approved_by'], row['posted_by'], row['posting_key'])
        actor = self.request.state.user_id.hex
        try:
            next_state = state.approve(actor) if action == 'approve' else state.submit(actor)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from None
        values = {'status': next_state.status, ('approved_by' if action == 'approve' else 'submitted_by'): actor,
                  ('approved_at' if action == 'approve' else 'submitted_at'): now(), 'updated_at': now()}
        await self.repo.update('inv_documents', identifier, values)
        self.request.state.audit_details = {'entity_type': 'inventory.document', 'entity_id': identifier, 'old': row, 'new': values}
        return {'id': identifier, **values}
