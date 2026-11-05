from datetime import date
from uuid import UUID
from fastapi import APIRouter, Depends, Request, Query, HTTPException
from sqlalchemy import text
from infrastructure.database.db_context import get_session
from ..domain.documents import Document, Posting, FinancialControls, Reversal, DocumentDecision
from ..application.document_service import DocumentService
from ..application.posting_service import InventoryPostingService
from ..application.inventory_service import InventoryService
from ..application.stock_service import StockService
from ..application.posting_access import warehouse
from decimal import Decimal
from collections import defaultdict
from core.access import require
from modules.module_equipment.integrations.inventory_source import (
    fuel_return_details,
    fuel_return_warehouse,
)

router = APIRouter(prefix='/api/v1/inventory', tags=['Inventory operations'])
async def operational_session(session=Depends(get_session, scope='function')):
    if not await session.scalar(text("SELECT 1 FROM sqlite_master WHERE type='table' AND name='inv_reservations'")):
        raise HTTPException(409, 'SETUP_MIGRATION_REQUIRED')
    if not await session.scalar(text("SELECT 1 FROM pragma_table_info('inv_documents') WHERE name='destination_warehouse_id'")):
        raise HTTPException(409, 'SETUP_MIGRATION_REQUIRED')
    if not await session.scalar(text("SELECT 1 FROM pragma_table_info('inv_documents') WHERE name='reason'")):
        raise HTTPException(409, 'SETUP_MIGRATION_REQUIRED')
    if not await session.scalar(text("SELECT 1 FROM sqlite_master WHERE name='inv_custody_accounts' AND type='table'")):
        raise HTTPException(409, 'SETUP_MIGRATION_REQUIRED')
    if not await session.scalar(text("SELECT 1 FROM pragma_table_info('inv_documents') WHERE name='source_stock_status'")):
        raise HTTPException(409, 'SETUP_MIGRATION_REQUIRED')
    if not await session.scalar(text("SELECT 1 FROM pragma_table_info('inv_documents') WHERE name='counterparty_reference'")):
        raise HTTPException(409, 'SETUP_MIGRATION_REQUIRED')
    if not await session.scalar(text("SELECT 1 FROM pragma_table_info('inv_documents') WHERE name='adjustment_kind'")):
        raise HTTPException(409, 'SETUP_MIGRATION_REQUIRED')
    if not await session.scalar(text("SELECT 1 FROM pragma_table_info('inv_documents') WHERE name='reverses_document_id'")):
        raise HTTPException(409, 'SETUP_MIGRATION_REQUIRED')
    if not await session.scalar(text("SELECT 1 FROM pragma_table_info('inv_documents') WHERE name='closed_by'")):
        raise HTTPException(409, 'SETUP_MIGRATION_REQUIRED')
    if not await session.scalar(text("SELECT 1 FROM pragma_table_info('inv_documents') WHERE name='stocktake_id'")):
        raise HTTPException(409, 'SETUP_MIGRATION_REQUIRED')
    return session


Session = Depends(operational_session, scope='function')


@router.post('/documents', status_code=201)
async def create(data: Document, request: Request, session=Session):
    return await DocumentService(session, request).save(data)


@router.post('/documents/equipment-fuel-returns/{event_id}', status_code=201)
async def create_equipment_fuel_return(
    event_id: UUID, organization_id: UUID, request: Request, session=Session,
):
    require(request, 'inventory.documents.create')
    await InventoryService(session, request)._check_org(organization_id.hex)
    source_warehouse_id = await fuel_return_warehouse(
        session, organization_id.hex, event_id.hex,
    )
    await warehouse(
        session, request, source_warehouse_id, 'inventory.documents.create',
    )
    details = await fuel_return_details(session, organization_id.hex, event_id.hex)
    event, issue = details['event'], details['issue']
    payload = Document(
        organization_id=organization_id,
        warehouse_id=UUID(issue['warehouse_id']),
        document_type='RECEIPT',
        document_date=date.fromisoformat(event['event_at'][:10]),
        source_module='equipment',
        source_type='fuel_return_event',
        source_id=event_id,
        lines=[{
            'item_id': UUID(issue['item_id']),
            'unit_id': UUID(issue['base_unit_id']),
            'quantity': event['quantity'],
            'transaction_currency': issue['valuation_currency'],
            'original_unit_price': format(details['unit_price'], 'f'),
        }],
    )
    created = await DocumentService(session, request).save(payload)
    return {**created, 'warehouse_id': issue['warehouse_id']}


@router.get('/documents')
async def listing(warehouse_id: UUID, request: Request, session=Session,
                  skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200)):
    await warehouse(session, request, warehouse_id.hex, 'inventory.documents.view')
    service = DocumentService(session, request)
    rows = await service.repo.many('SELECT d.*,COUNT(l.id) AS line_count FROM inv_documents d '
        'LEFT JOIN inv_document_lines l ON l.document_id=d.id WHERE d.warehouse_id=:w GROUP BY d.id '
        'ORDER BY d.created_at DESC,d.id LIMIT :l OFFSET :s', w=warehouse_id.hex, l=limit, s=skip)
    result = []
    for row in rows:
        if row.get('destination_warehouse_id'):
            try:
                await warehouse(session, request, row['destination_warehouse_id'], 'inventory.documents.view')
            except HTTPException as exc:
                if exc.status_code in (403, 404, 409):
                    continue
                raise
        result.append(row)
    return {'items': result}


@router.get('/transfer-dispatch-lines')
async def dispatch_lines(warehouse_id: UUID, request: Request, session=Session):
    await warehouse(session, request, warehouse_id.hex, 'inventory.documents.view')
    service = DocumentService(session, request)
    lines = await service.repo.many("SELECT l.id,l.item_id,l.location_id,l.destination_location_id,l.base_quantity,d.id AS document_id,d.document_no,d.destination_warehouse_id FROM inv_document_lines l JOIN inv_effective_documents d ON d.id=l.document_id WHERE d.warehouse_id=:w AND d.document_type='TRANSFER_DISPATCH' AND d.status IN ('POSTED','CLOSED') ORDER BY d.created_at DESC,l.line_no LIMIT 200", w=warehouse_id.hex)
    received = defaultdict(Decimal)
    receipts = await service.repo.many("SELECT l.dispatch_line_id,l.base_quantity FROM inv_document_lines l JOIN inv_effective_documents d ON d.id=l.document_id WHERE d.warehouse_id=:w AND d.status IN ('POSTED','CLOSED') AND d.document_type IN ('TRANSFER_RECEIPT','LOSS_TRANSIT')", w=warehouse_id.hex)
    for receipt in receipts:
        received[receipt['dispatch_line_id']] += Decimal(receipt['base_quantity'])
    result = []
    for line in lines:
        try:
            await warehouse(session, request, line['destination_warehouse_id'], 'inventory.documents.view')
        except HTTPException as exc:
            if exc.status_code in (403, 404, 409):
                continue
            raise
        remaining = Decimal(line['base_quantity']) - received[line['id']]
        result.append({**line, 'remaining_in_transit': str(remaining)})
    return {'items': result}


@router.get('/custody/holders')
async def custody_holders(warehouse_id: UUID, request: Request, session=Session):
    from ..application.custody_service import CustodyPosting
    return await CustodyPosting(session,request).holders(warehouse_id.hex)


@router.get('/receipt-lines')
async def supplier_receipt_lines(warehouse_id: UUID,request: Request,session=Session):
    from ..application.supplier_return_service import SupplierReturnPosting
    return await SupplierReturnPosting(session,request).references(warehouse_id.hex)


@router.get('/value-correction-origins')
async def value_correction_origins(warehouse_id: UUID,request: Request,session=Session):
    from ..application.value_correction_service import ValueCorrectionPosting
    return await ValueCorrectionPosting(session,request).references(warehouse_id.hex)


@router.get('/custody/origins')
async def custody_origins(warehouse_id: UUID, request: Request, session=Session):
    from ..application.custody_service import CustodyPosting
    return await CustodyPosting(session,request).report(warehouse_id.hex,references=True)


@router.get('/custody')
async def custody_report(warehouse_id: UUID, request: Request, session=Session,
                         skip: int = Query(0,ge=0),limit: int = Query(200,ge=1,le=200)):
    from ..application.custody_service import CustodyPosting
    return await CustodyPosting(session,request).report(warehouse_id.hex,skip=skip,limit=limit)


@router.get('/document-actions')
async def document_actions(warehouse_id: UUID, request: Request, document_id: UUID | None = None, document_type: str | None = None, session=Session):
    await warehouse(session,request,warehouse_id.hex,'inventory.documents.view')
    targets=[warehouse_id.hex]
    if document_id:
        doc=await DocumentService(session,request).raw(document_id.hex,'inventory.documents.view')
        if doc['warehouse_id']!=warehouse_id.hex:
            raise HTTPException(404,'DOCUMENT_WAREHOUSE_MISMATCH')
        if doc.get('destination_warehouse_id'):
            targets.append(doc['destination_warehouse_id'])
        document_type=doc['document_type']
        if document_type=='REVERSAL':
            from ..application.reversal_service import ReversalPosting
            try:
                await ReversalPosting(session,request).original(doc['reverses_document_id'])
            except HTTPException as exc:
                if exc.status_code not in (403,404,409):raise
                return {'create':False,'approve':False,'post':False}
    if document_type=='ADJUSTMENT':
        from ..application.value_correction_service import authorize,ValueCorrectionPosting
        wh=await DocumentService(session,request).repo.one('SELECT organization_id FROM inv_warehouses WHERE id=:i',i=warehouse_id.hex)
        try:
            if document_id and doc['adjustment_kind']=='COUNT':
                from ..application.count_posting import CountPosting
                await CountPosting(session,request).authorize_document_sources(doc)
            else:
                authorize(request,wh['organization_id'])
                if document_id:await ValueCorrectionPosting(session,request).authorize_document_sources(doc)
        except HTTPException as exc:
            if exc.status_code!=403:raise
            return {'create':False,'approve':False,'post':False}
    result={}
    for action in ('create','approve','post'):
        result[action]=True
        for target in targets:
            try:
                await warehouse(session,request,target,'inventory.documents.'+action)
            except HTTPException as exc:
                if exc.status_code not in (403,404):
                    raise
                result[action]=False
    return result


@router.get('/documents/{identifier}')
async def detail(identifier: UUID, request: Request, session=Session):
    return await DocumentService(session, request).detail(identifier.hex)


@router.put('/documents/{identifier}')
async def update(identifier: UUID, data: Document, request: Request, session=Session):
    return await DocumentService(session, request).save(data, identifier.hex)


@router.post('/documents/{identifier}/submit')
async def submit(identifier: UUID, request: Request, session=Session):
    return await DocumentService(session, request).transition(identifier.hex, 'submit')


@router.post('/documents/{identifier}/reverse',status_code=201)
async def reverse_document(identifier:UUID,data:Reversal,request:Request,session=Session):
    from ..application.reversal_service import ReversalPosting
    return await ReversalPosting(session,request).create(identifier.hex,data)


@router.get('/documents/{identifier}/reversal-options')
async def reversal_options(identifier:UUID,request:Request,session=Session):
    from ..application.reversal_service import ReversalPosting
    doc=await DocumentService(session,request).raw(identifier.hex,'inventory.documents.view')
    service=ReversalPosting(session,request)
    try:
        await service.original(identifier.hex)
        await warehouse(session,request,doc['warehouse_id'],'inventory.documents.create')
        if doc.get('destination_warehouse_id'):
            await warehouse(session,request,doc['destination_warehouse_id'],'inventory.documents.create')
        await service.eligible(doc)
    except HTTPException as exc:
        if exc.status_code not in (403,404,409):raise
        return {'enabled':False,'reason':exc.detail if exc.status_code==409 else 'REVERSAL_PERMISSION_REQUIRED'}
    return {'enabled':True,'reason':None}


@router.post('/documents/{identifier}/approve')
async def approve(identifier: UUID, request: Request, session=Session):
    return await DocumentService(session, request).transition(identifier.hex, 'approve')


@router.post('/documents/{identifier}/post')
async def post(identifier: UUID, data: Posting, request: Request, session=Session):
    return await InventoryPostingService(session, request).post(identifier.hex, data.idempotency_key)


@router.post('/documents/{identifier}/{decision}')
async def document_decision(identifier:UUID,decision:str,data:DocumentDecision,request:Request,session=Session):
    if decision not in ('reject','cancel','revise','close'):raise HTTPException(404,'UNKNOWN_DOCUMENT_ACTION')
    from ..application.document_lifecycle import DocumentLifecycle
    return await DocumentLifecycle(session,request).decide(identifier.hex,decision,data)


@router.get('/documents/{identifier}/lifecycle-actions')
async def lifecycle_actions(identifier:UUID,request:Request,session=Session):
    doc=await DocumentService(session,request).raw(identifier.hex,'inventory.documents.view')
    from ..domain.document_policy import DocumentState
    state=DocumentState(doc['created_by'],doc['status'],doc['approved_by'],doc['posted_by'],doc['posting_key'])
    result={}
    for action,permission in [('reject','approve'),('cancel','create'),('revise','create'),('close','close')]:
        try:
            await DocumentService(session,request).raw(identifier.hex,'inventory.documents.'+permission)
            getattr(state,action)(request.state.user_id.hex)
            result[action]=not(action=='cancel' and doc.get('source_module'))
        except ValueError:result[action]=False
        except HTTPException as exc:
            if exc.status_code not in (403,404,409):raise
            result[action]=False
    return result


@router.put('/financial-controls/{legal_entity_id}')
async def controls(legal_entity_id: UUID, data: FinancialControls, request: Request, session=Session):
    return await StockService(session, request).controls(legal_entity_id.hex, data)


@router.get('/balances')
async def balances(warehouse_id: UUID, request: Request, session=Session):
    return await StockService(session, request).balances(warehouse_id.hex)


@router.get('/movements')
async def movements(warehouse_id: UUID, request: Request, session=Session,
                    skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200)):
    return await StockService(session, request).movements(warehouse_id.hex, skip, limit)


@router.get('/reports/reconciliation')
async def reconciliation(warehouse_id: UUID, request: Request, session=Session):
    return await StockService(session, request).reconciliation(warehouse_id.hex)
