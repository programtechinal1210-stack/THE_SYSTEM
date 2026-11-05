"""Operational forms use the existing shared HTTP client and Core shell."""
from uuid import UUID, uuid4
from urllib.parse import urlencode
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from shared.services.api_client import ApiClient, ApiException, UnauthorizedException, ForbiddenException, NotFoundException
from .reports import page as reports_page


@require_http_methods(['GET','POST'])
def page(request,mode_override=None):
    api = ApiClient(token=request.session.get('access_token'))
    try:
        identity = api.get('/auth/me')
        can = lambda p: identity.get('is_admin') or p in identity.get('permissions', [])
        work = api.get('/profile/work-context')
        organization = work.get('selected_id')
        mode = mode_override or request.GET.get('mode', 'documents')
        permission = {'documents':'inventory.documents.view','balances':'inventory.stock.view',
                      'movements':'inventory.stock.view','custody':'inventory.stock.view','reconciliation':'inventory.reports.view'}.get(mode)
        if not permission or not can(permission):
            return HttpResponse('القسم غير متاح ضمن صلاحياتك',status=403)
        warehouses = api.get('/inventory/warehouses',params={'organization_id':organization,'limit':200})['items'] if organization else []
        selected = request.POST.get('warehouse_id') or request.GET.get('warehouse_id') or (warehouses[0]['id'] if warehouses else '')
        if selected:
            selected = UUID(selected).hex
            if selected not in {w['id'] for w in warehouses}:
                return HttpResponse('المخزن غير متاح ضمن الجهة الحالية',status=403)
        if mode == 'reconciliation':
            return reports_page(request, api, identity, work, warehouses, organization, selected)
        base = reverse('inventory:operations') + '?' + urlencode({'mode':mode,'warehouse_id':selected})
        identifier = UUID(request.GET['document']).hex if request.GET.get('document') else ''
        actions={'create':False,'approve':False,'post':False}
        lifecycle={'reject':False,'cancel':False,'revise':False,'close':False}
        if selected and can('inventory.documents.view'):
            try:
                parameters={'warehouse_id':selected}
                if identifier:parameters['document_id']=identifier
                selected_type=request.POST.get('document_type') or request.GET.get('document_type')
                if selected_type:parameters['document_type']=selected_type
                actions=api.get('/inventory/document-actions',params=parameters)
                if identifier:lifecycle=api.get('/inventory/documents/'+identifier+'/lifecycle-actions')
            except (ForbiddenException,NotFoundException):
                pass
        error = ''
        error_status = 200
        posted_lines = []
        if request.method == 'POST':
            command = request.POST.get('command')
            needed = {'save':'inventory.documents.create','submit':'inventory.documents.create',
                      'approve':'inventory.documents.approve','post':'inventory.documents.post','reverse':'inventory.documents.reverse',
                      'reject':'inventory.documents.approve','cancel':'inventory.documents.create','revise':'inventory.documents.create','close':'inventory.documents.close'}.get(command)
            scoped_action={'save':'create','submit':'create','approve':'approve','post':'post','reverse':'create'}.get(command)
            scoped_allowed=lifecycle.get(command) if command in lifecycle else actions.get(scoped_action)
            if not needed or not can(needed) or not scoped_allowed:
                return HttpResponse('ليس لديك صلاحية تنفيذ هذا الإجراء',status=403)
            try:
                if command == 'save':
                    kind = request.POST.get('document_type','RECEIPT')
                    item_ids=request.POST.getlist('item_id'); quantities=request.POST.getlist('quantity')
                    prices=request.POST.getlist('original_unit_price'); currencies=request.POST.getlist('transaction_currency')
                    locations=request.POST.getlist('location_id')
                    sources=request.POST.getlist('request_line_id')
                    dispatches=request.POST.getlist('dispatch_line_id')
                    destination_locations=request.POST.getlist('destination_location_id')
                    origins=request.POST.getlist('origin_line_id')
                    supplier_lines=request.POST.getlist('supplier_line_id')
                    value_origins=request.POST.getlist('value_origin_id')
                    value_amounts=request.POST.getlist('value_adjustment_amount')
                    custody_locations=request.POST.getlist('custody_location_id')
                    for index,item in enumerate(item_ids):
                        line={'item_id':item,'quantity':quantities[index] if index<len(quantities) else '',
                              'location_id': locations[index] or None if index<len(locations) else None}
                        if kind=='RECEIPT':
                            line.update(original_unit_price=prices[index] if index<len(prices) else '',
                                        transaction_currency=currencies[index] if index<len(currencies) else '')
                        elif kind in ('TRANSFER_RECEIPT','LOSS_TRANSIT'):
                            line['dispatch_line_id']=dispatches[index] if index<len(dispatches) else ''
                            line['destination_location_id']=destination_locations[index] or None if index<len(destination_locations) else None
                        elif kind in ('ISSUE_DIRECT','ISSUE_CUSTODY') and index<len(sources) and sources[index]:
                            line['request_line_id']=sources[index]
                        if kind in ('ISSUE_CUSTODY','RETURN_INTERNAL'):
                            line['destination_location_id']=custody_locations[index] or None if index<len(custody_locations) else None
                        if kind in ('CONSUMPTION','RETURN_INTERNAL'):
                            line['origin_line_id']=origins[index] if index<len(origins) else ''
                        if kind=='RETURN_SUPPLIER':
                            line['origin_line_id']=supplier_lines[index] if index<len(supplier_lines) else ''
                        if kind=='ADJUSTMENT':
                            line['origin_line_id']=value_origins[index] if index<len(value_origins) else ''
                            line['value_adjustment_amount']=value_amounts[index] if index<len(value_amounts) else ''
                        posted_lines.append(line)
                    data={'organization_id':organization,'warehouse_id':selected,'document_type':kind,
                          'document_date':request.POST.get('document_date'),'lines':posted_lines}
                    if kind.startswith('TRANSFER_') or kind=='LOSS_TRANSIT':
                        data['destination_warehouse_id']=request.POST.get('destination_warehouse_id')
                    if kind in ('LOSS_TRANSIT','STATUS_CHANGE','SCRAP','RETURN_SUPPLIER','ADJUSTMENT'):
                        data['reason']=request.POST.get('reason','')
                    if kind=='RETURN_SUPPLIER':data['counterparty_reference']=request.POST.get('counterparty_reference','')
                    if kind=='ADJUSTMENT':data['adjustment_kind']='VALUE'
                    if kind in ('STATUS_CHANGE','SCRAP'):
                        data['source_stock_status']=request.POST.get('source_stock_status')
                        if kind=='STATUS_CHANGE':data['target_stock_status']=request.POST.get('target_stock_status')
                    if kind in ('ISSUE_CUSTODY','CONSUMPTION','RETURN_INTERNAL'):
                        data['beneficiary_user_id']=request.POST.get('beneficiary_user_id')
                    if kind=='ISSUE_CUSTODY':
                        data['custody_due_date']=request.POST.get('custody_due_date') or None
                    saved=api.put('/inventory/documents/'+identifier,data) if identifier else api.post('/inventory/documents',data)
                    identifier=saved['id']
                elif command in lifecycle:
                    identifier=UUID(request.POST.get('document_id','')).hex
                    api.post('/inventory/documents/'+identifier+'/'+command,{'reason':request.POST.get('decision_reason','')})
                elif command=='reverse':
                    original=UUID(request.POST.get('document_id','')).hex
                    saved=api.post('/inventory/documents/'+original+'/reverse',{'document_date':request.POST.get('reversal_date'),'reason':request.POST.get('reversal_reason','')})
                    identifier=saved['id']
                else:
                    identifier=UUID(request.POST.get('document_id','')).hex
                    body={'idempotency_key':request.POST.get('posting_key','')} if command=='post' else {}
                    api.post('/inventory/documents/'+identifier+'/'+command,body)
                return HttpResponseRedirect(base+'&document='+identifier)
            except (ApiException,ValueError,IndexError) as exc:
                error='تعذر تنفيذ العملية: '+str(exc)
                error_status=422 if command=='save' else 409
        records=[];document=None;items=[];locations=[];report=None;currencies=[];request_lines=[];dispatch_lines=[];holders=[];custody_origins=[];receipt_lines=[];value_origins=[];can_correct_value=False;balance_preview=[];balance_visible=False
        balance_items=[];balance_locations=[];balance_categories=[];balance_units=[];balance_summary={};balance_search=request.GET.get('balance_search','').strip();balance_category=request.GET.get('balance_category','').strip();balance_status=request.GET.get('balance_status','').strip();balance_location=request.GET.get('balance_location','').strip();balance_error=''
        movement_items=[];movement_locations=[];movement_units=[];movement_documents=[];movement_types=[];movement_summary={};movement_search=request.GET.get('movement_search','').strip();movement_type=request.GET.get('movement_type','').strip();movement_from=request.GET.get('movement_from','').strip();movement_to=request.GET.get('movement_to','').strip();movement_error=''
        custody_tab=request.GET.get('custody_tab','active').strip() or 'active';custody_search=request.GET.get('custody_search','').strip();custody_holder=request.GET.get('custody_holder','').strip();custody_status=request.GET.get('custody_status','').strip();custody_item=request.GET.get('custody_item','').strip();custody_holders=[];custody_items=[];custody_documents=[];custody_summary={};custody_error=''
        reversal_options={'enabled':False}
        readiness=api.get('/inventory/warehouses/'+selected+'/readiness') if selected else {}
        document_type_filter=request.GET.get('document_type','').strip().upper()
        status_filter=request.GET.get('status','').strip().upper()
        search=request.GET.get('search','').strip()
        page_number=max(1,int(request.GET.get('page','1') or 1))
        page_size=10
        all_document_records=[];counts={};total_documents=0;page_count=1
        document_type_labels={'RECEIPT':'استلام مواد','ISSUE_DIRECT':'صرف مواد','ISSUE_CUSTODY':'تسليم عهدة','TRANSFER_DIRECT':'تحويل مواد','TRANSFER_DISPATCH':'إرسال تحويل مرحلي','TRANSFER_RECEIPT':'استلام تحويل','RETURN_INTERNAL':'مرتجع داخلي','RETURN_SUPPLIER':'مرتجع مورد','CONSUMPTION':'استهلاك عهدة','ADJUSTMENT':'تسوية','STATUS_CHANGE':'تغيير حالة','SCRAP':'إتلاف','REVERSAL':'عكس مستند','LOSS_TRANSIT':'فاقد أثناء النقل'}
        document_status_labels={'DRAFT':'مسودة','SUBMITTED':'بانتظار الاعتماد','APPROVED':'بانتظار الترحيل','POSTED':'مرحّل','CLOSED':'مغلق','REJECTED':'مرفوض','CANCELLED':'ملغى'}
        if selected:
            endpoint={'documents':'documents','balances':'balances','movements':'movements','custody':'custody','reconciliation':'reports/reconciliation'}[mode]
            data=api.get('/inventory/'+endpoint,params={'warehouse_id':selected,'limit':200} if mode in ('documents','movements') else {'warehouse_id':selected})
            if mode=='reconciliation':report=data
            else:records=data['items']
            if mode=='documents':
                all_document_records=list(records)
                warehouse_names={str(row.get('id')).replace('-',''):row.get('name_ar') or row.get('name') or row.get('code') or 'المخزن الحالي' for row in warehouses}
                for row in all_document_records:
                    row['type_label']=document_type_labels.get(row.get('document_type'),'عملية مخزنية')
                    row['status_label']=document_status_labels.get(row.get('status'),'قيد المعالجة')
                    row['warehouse_label']=warehouse_names.get(str(row.get('warehouse_id','')).replace('-',''),'المخزن الحالي')
                    if row.get('destination_warehouse_id'):
                        destination=warehouse_names.get(str(row['destination_warehouse_id']).replace('-',''),'مخزن الوجهة')
                        row['warehouse_label']=row['warehouse_label']+' ← '+destination
                    row['reference_label']=row.get('counterparty_reference') or row.get('source_type') or '—'
                counts={key:sum(row.get('status')==key for row in all_document_records) for key in document_status_labels}
                visible=[row for row in all_document_records if (not document_type_filter or row.get('document_type')==document_type_filter) and (not status_filter or row.get('status')==status_filter) and (not search or search.casefold() in ' '.join(str(row.get(key,'')) for key in ('document_no','document_type','warehouse_id','counterparty_reference','source_type')).casefold())]
                total_documents=len(visible)
                page_count=max(1,(total_documents+page_size-1)//page_size)
                page_number=min(page_number,page_count)
                records=visible[(page_number-1)*page_size:page_number*page_size]
            else:
                counts={};total_documents=len(records);page_count=1
            if mode=='movements':
                try:
                    movement_items=api.get('/inventory/items',params={'organization_id':organization,'limit':200}).get('items',[])
                    movement_units=api.get('/inventory/units',params={'organization_id':organization,'limit':200}).get('items',[])
                    movement_locations=api.get('/inventory/warehouses/'+selected+'/locations').get('items',[])
                    movement_documents=api.get('/inventory/documents',params={'warehouse_id':selected,'limit':200}).get('items',[])
                except (ApiException, KeyError, TypeError):
                    movement_error='تعذر تحميل مراجع الحركات. أعد المحاولة.'
                item_by_id={str(row.get('id','')).replace('-',''):row for row in movement_items}
                unit_by_id={str(row.get('id','')).replace('-',''):row for row in movement_units}
                location_by_id={str(row.get('id','')).replace('-',''):row for row in movement_locations}
                document_by_id={str(row.get('id','')).replace('-',''):row for row in movement_documents}
                movement_type_labels={'RECEIPT':'استلام','ISSUE_DIRECT':'صرف','ISSUE_CUSTODY':'تسليم عهدة','TRANSFER_DIRECT':'تحويل مباشر','TRANSFER_DISPATCH':'تحويل صادر','TRANSFER_RECEIPT':'تحويل وارد','RETURN_INTERNAL':'مرتجع داخلي','RETURN_SUPPLIER':'مرتجع مورد','CONSUMPTION':'استهلاك عهدة','ADJUSTMENT':'تسوية','STATUS_CHANGE':'تغيير حالة','SCRAP':'إتلاف','REVERSAL':'عكس مستند','LOSS_TRANSIT':'فاقد أثناء النقل'}
                prepared=[]
                for row in records:
                    item=item_by_id.get(str(row.get('item_id','')).replace('-',''),{})
                    location=location_by_id.get(str(row.get('location_id','')).replace('-',''),{}) if row.get('location_id') else {}
                    document=document_by_id.get(str(row.get('posting_group_id','')).replace('-',''),{})
                    document_type=document.get('document_type','')
                    delta=str(row.get('quantity_delta','0'))
                    try: direction='in' if float(delta)>0 else 'out' if float(delta)<0 else 'neutral'
                    except (TypeError,ValueError): direction='neutral'
                    row.update({'item_name':item.get('name_ar') or item.get('name') or row.get('item_id',''),
                                'item_code':item.get('code') or '',
                                'unit_name':unit_by_id.get(str(item.get('base_unit_id','')).replace('-',''),{}).get('name') or unit_by_id.get(str(item.get('base_unit_id','')).replace('-',''),{}).get('code') or 'الوحدة الأساسية',
                                'location_name':location.get('name') or location.get('code') or 'دون موقع محدد',
                                'location_code':location.get('code') or '',
                                'document_id':row.get('posting_group_id') or '',
                                'document_no':document.get('document_no') or 'مرجع الحركة غير متاح',
                                'document_type':document_type,
                                'movement_type_label':movement_type_labels.get(document_type,'حركة مخزنية'),
                                'direction':direction,
                                'movement_status':'مرحّل'})
                    posted_at=str(row.get('posted_at') or '')
                    searchable=' '.join(str(row.get(key,'')) for key in ('item_name','item_code','document_no','ledger_seq')).casefold()
                    if movement_search and movement_search.casefold() not in searchable: continue
                    if movement_type and document_type != movement_type: continue
                    if movement_from and posted_at[:10] < movement_from: continue
                    if movement_to and posted_at[:10] > movement_to: continue
                    prepared.append(row)
                records=prepared
                movement_types=[{'value':key,'label':value} for key,value in movement_type_labels.items()]
                movement_summary={'movement_count':len(records),'document_count':len({str(row.get('posting_group_id','')) for row in records if row.get('posting_group_id')}),'item_count':len({str(row.get('item_id','')) for row in records})}
                total_documents=len(records)
                page_count=max(1,(total_documents+page_size-1)//page_size)
                page_number=min(page_number,page_count)
                records=records[(page_number-1)*page_size:page_number*page_size]
            elif mode=='custody':
                try:
                    custody_holders=api.get('/inventory/custody/holders',params={'warehouse_id':selected}).get('items',[])
                    custody_items=api.get('/inventory/items',params={'organization_id':organization,'limit':200}).get('items',[])
                    custody_documents=api.get('/inventory/documents',params={'warehouse_id':selected,'limit':200}).get('items',[])
                except (ApiException, KeyError, TypeError):
                    custody_error='تعذر تحميل بيانات العهدة. أعد المحاولة.'
                active_report=list(records)
                document_type_labels={'ISSUE_CUSTODY':'تسليم عهدة','CONSUMPTION':'استهلاك عهدة','RETURN_INTERNAL':'مرتجع عهدة'}
                item_by_id={str(row.get('id','')).replace('-',''):row for row in custody_items}
                holder_by_id={str(row.get('id','')).replace('-',''):row for row in custody_holders}
                issued_docs=[row for row in custody_documents if row.get('document_type')=='ISSUE_CUSTODY' and row.get('status') in ('POSTED','CLOSED')]
                consumption_docs=[row for row in custody_documents if row.get('document_type')=='CONSUMPTION' and row.get('status') in ('POSTED','CLOSED')]
                return_docs=[row for row in custody_documents if row.get('document_type')=='RETURN_INTERNAL' and row.get('status') in ('POSTED','CLOSED')]
                for row in active_report:
                    row['custody_status_label']='عهدة مستهلكة بالكامل' if row.get('status')=='SETTLED' else ('عهدة غير متسقة' if row.get('status')=='INCONSISTENT_CUSTODY' else ('عهدة جزئية' if row.get('consumed') not in ('0','0.0','0.00') or row.get('returned') not in ('0','0.0','0.00') else 'نشطة'))
                    row['next_action']='عرض التفاصيل' if row.get('status') in ('SETTLED','INCONSISTENT_CUSTODY') or not can('inventory.documents.create') else ('تسجيل إرجاع' if row.get('consumed') not in ('0','0.0','0.00') and row.get('remaining') not in ('0','0.0','0.00') else 'تسجيل استهلاك أو إرجاع')
                pending_rows=[]
                for row in custody_documents:
                    if row.get('document_type')=='ISSUE_CUSTODY' and row.get('status') in ('DRAFT','SUBMITTED','APPROVED'):
                        pending_rows.append({'id':row.get('id'),'document_id':row.get('id'),'document_no':row.get('document_no'),'holder_user_id':row.get('beneficiary_user_id'),'holder_name':holder_by_id.get(str(row.get('beneficiary_user_id','')).replace('-',''),{}).get('name') or 'المستفيد غير متاح','item_name':'تفاصيل البنود داخل المستند','item_code':'','issued':'—','consumed':'—','returned':'—','remaining':'—','status':'PENDING','custody_status_label':'بانتظار الاستلام','next_action':'استكمال التسليم' if can('inventory.documents.create') else 'عرض التفاصيل','document_type_label':document_type_labels['ISSUE_CUSTODY']})
                if custody_tab=='active':
                    prepared=pending_rows+active_report
                elif custody_tab=='issue':
                    prepared=[{'id':row.get('id'),'document_id':row.get('id'),'document_no':row.get('document_no'),'holder_name':holder_by_id.get(str(row.get('beneficiary_user_id','')).replace('-',''),{}).get('name') or 'المستفيد غير متاح','item_name':'تفاصيل البنود داخل المستند','item_code':'','issued':'—','consumed':'—','returned':'—','remaining':'—','status':'POSTED','custody_status_label':'مرحّل','next_action':'عرض التفاصيل','document_type_label':document_type_labels['ISSUE_CUSTODY']} for row in issued_docs]
                elif custody_tab=='consumption':
                    prepared=[{'id':row.get('id'),'document_id':row.get('id'),'document_no':row.get('document_no'),'holder_name':holder_by_id.get(str(row.get('beneficiary_user_id','')).replace('-',''),{}).get('name') or 'المستفيد غير متاح','item_name':'تفاصيل البنود داخل المستند','item_code':'','issued':'—','consumed':'—','returned':'—','remaining':'—','status':'POSTED','custody_status_label':'مرحّل','next_action':'عرض التفاصيل','document_type_label':document_type_labels['CONSUMPTION']} for row in consumption_docs]
                elif custody_tab=='returns':
                    prepared=[{'id':row.get('id'),'document_id':row.get('id'),'document_no':row.get('document_no'),'holder_name':holder_by_id.get(str(row.get('beneficiary_user_id','')).replace('-',''),{}).get('name') or 'المستفيد غير متاح','item_name':'تفاصيل البنود داخل المستند','item_code':'','issued':'—','consumed':'—','returned':'—','remaining':'—','status':'POSTED','custody_status_label':'مرحّل','next_action':'عرض التفاصيل','document_type_label':document_type_labels['RETURN_INTERNAL']} for row in return_docs]
                else:
                    prepared=[]
                filtered=[]
                for row in prepared:
                    searchable=' '.join(str(row.get(key,'')) for key in ('holder_name','item_name','item_code','document_no')).casefold()
                    if custody_search and custody_search.casefold() not in searchable: continue
                    if custody_holder and str(row.get('holder_user_id','')).replace('-','') != custody_holder.replace('-',''): continue
                    if custody_item and str(row.get('item_id','')).replace('-','') != custody_item.replace('-',''): continue
                    if custody_status and row.get('status') != custody_status: continue
                    filtered.append(row)
                records=filtered
                custody_summary={'active_count':sum(row.get('status')=='OPEN' for row in active_report),'pending_count':sum(row.get('status') in ('DRAFT','SUBMITTED','APPROVED') for row in custody_documents if row.get('document_type')=='ISSUE_CUSTODY'),'closed_count':sum(row.get('status') in ('SETTLED','CLOSED') for row in active_report),'return_count':len(return_docs)}
                total_documents=len(records)
                page_count=max(1,(total_documents+page_size-1)//page_size)
                page_number=min(page_number,page_count)
                records=records[(page_number-1)*page_size:page_number*page_size]
            elif mode=='balances':
                try:
                    balance_items=api.get('/inventory/items',params={'organization_id':organization,'limit':200}).get('items',[])
                    balance_categories=api.get('/inventory/categories',params={'organization_id':organization,'limit':200}).get('items',[])
                    balance_units=api.get('/inventory/units',params={'organization_id':organization,'limit':200}).get('items',[])
                    balance_locations=api.get('/inventory/warehouses/'+selected+'/locations').get('items',[])
                except (ApiException, KeyError, TypeError):
                    balance_error='تعذر تحميل أسماء الأصناف والمواقع. أعد المحاولة.'
                item_by_id={str(row.get('id','')).replace('-',''):row for row in balance_items}
                category_by_id={str(row.get('id','')).replace('-',''):row for row in balance_categories}
                unit_by_id={str(row.get('id','')).replace('-',''):row for row in balance_units}
                location_by_id={str(row.get('id','')).replace('-',''):row for row in balance_locations}
                prepared=[]
                for row in records:
                    item=item_by_id.get(str(row.get('item_id','')).replace('-',''),{})
                    location=location_by_id.get(str(row.get('location_id','')).replace('-',''),{}) if row.get('location_id') else {}
                    category=category_by_id.get(str(item.get('category_id','')).replace('-',''),{}) if item.get('category_id') else {}
                    unit=unit_by_id.get(str(item.get('base_unit_id','')).replace('-',''),{}) if item.get('base_unit_id') else {}
                    row.update({'item_name':item.get('name_ar') or item.get('name') or row.get('item_id',''),
                                'item_code':item.get('code') or '', 'category_name':category.get('name_ar') or category.get('name') or 'غير مصنف',
                                'unit_name':unit.get('name') or unit.get('code') or 'الوحدة الأساسية',
                                'location_name':location.get('name') or location.get('code') or 'دون موقع محدد',
                                'location_code':location.get('code') or '', 'warehouse_name':next((w.get('name_ar') or w.get('name') or w.get('code','') for w in warehouses if str(w.get('id','')).replace('-','')==selected),'المخزن الحالي')})
                    needle=balance_search.casefold()
                    searchable=' '.join(str(row.get(key,'')) for key in ('item_name','item_code','category_name','location_name')).casefold()
                    if needle and needle not in searchable: continue
                    if balance_category and str(item.get('category_id','')).replace('-','') != balance_category.replace('-',''): continue
                    if balance_status and row.get('stock_status') != balance_status: continue
                    if balance_location and str(row.get('location_id','')).replace('-','') != balance_location.replace('-',''): continue
                    prepared.append(row)
                records=prepared
                total_documents=len(records)
                balance_summary={'item_count':len({str(row.get('item_id','')) for row in records}),
                                 'balance_count':len(records),
                                 'available_count':sum(row.get('stock_status')=='AVAILABLE' and str(row.get('available_to_issue','0')) not in ('0','0.0','0.00') for row in records),
                                 'reserved_count':sum(str(row.get('active_reserved','0')) not in ('0','0.0','0.00') for row in records),
                                 'transit_count':sum(row.get('stock_status') in ('IN_TRANSIT','TRANSIT') for row in records)}
            else:
                balance_summary={}
            if identifier:
                document=api.get('/inventory/documents/'+identifier)
                if document['status'] in ('POSTED','CLOSED') and can('inventory.documents.reverse'):
                    reversal_options=api.get('/inventory/documents/'+identifier+'/reversal-options')
                if document['warehouse_id']!=selected:
                    return HttpResponse('المستند لا يتبع المخزن المختار',status=403)
            if mode=='documents' and actions.get('create'):
                if can('inventory.stock.view'):
                    try:
                        stock=api.get('/inventory/balances',params={'warehouse_id':selected})['items']
                        balance_preview=[{k:r[k] for k in ('item_id','location_id','stock_status','on_hand','available_to_issue','active_reserved')} for r in stock]
                        balance_visible=True
                    except (ForbiddenException,NotFoundException):
                        pass
                holders=api.get('/inventory/custody/holders',params={'warehouse_id':selected})['items']
                custody_origins=api.get('/inventory/custody/origins',params={'warehouse_id':selected})['items']
                receipt_lines=api.get('/inventory/receipt-lines',params={'warehouse_id':selected})['items']
                if can('inventory.valuation.correct'):
                    try:
                        value_origins=api.get('/inventory/value-correction-origins',params={'warehouse_id':selected})['items']
                        can_correct_value=True
                    except (ForbiddenException,NotFoundException):
                        pass
                dispatch_lines=api.get('/inventory/transfer-dispatch-lines',params={'warehouse_id':selected})['items']
                items=api.get('/inventory/items',params={'organization_id':organization,'limit':200})['items']
                locations=api.get('/inventory/warehouses/'+selected+'/locations')['items']
                currencies=api.get('/currency/currencies') if can('core.currency.view') else []
                if can('inventory.requests.view'):
                    request_lines=api.get('/inventory/request-lines',params={'organization_id':organization})['items']
        shortcuts=[]
        if mode=='documents' and selected:
            for key,title,description,icon in (('RECEIPT','استلام مواد','إضافة مواد واردة إلى المخزن','↓'),('ISSUE_DIRECT','صرف مواد','صرف مواد لجهة أو مشروع','↑'),('TRANSFER_DIRECT','تحويل مواد','نقل مواد بين المخازن','↔'),('RETURN_INTERNAL','مرتجع مواد','إرجاع مواد إلى المخزن','↩')):
                available=False
                if can('inventory.documents.create'):
                    try: available=bool(api.get('/inventory/document-actions',params={'warehouse_id':selected,'document_type':key}).get('create'))
                    except (ForbiddenException,NotFoundException): pass
                shortcuts.append({'key':key,'title':title,'description':description,'icon':icon,'available':available})
        lines=posted_lines or (document['lines'] if document and document['status']=='DRAFT' else [{}])
        beneficiary=request.POST.get('beneficiary_user_id') or (document.get('beneficiary_user_id') if document else '')
        if request.method=='GET' and request.GET.get('origin_line') and not document:
            origin_id=UUID(request.GET['origin_line']).hex
            origin=next((r for r in custody_origins if r['id']==origin_id),None)
            if not origin:return HttpResponse('مرجع العهدة غير متاح ضمن المخزن الحالي',status=404)
            lines=[{'item_id':origin['item_id'],'location_id':origin['location_id'],'origin_line_id':origin['id']}]
            beneficiary=origin['holder_user_id']
        for line in lines:
            if document and line.get('transaction_currency_id'):
                line['transaction_currency']=next((c['code'] for c in currencies if c['id'].replace('-','')==line['transaction_currency_id']),'')
        actor=identity.get('id','').replace('-','')
        creator=document and document['created_by']==actor
        document_type_label=document_type_labels.get(document.get('document_type'),'عملية مخزنية') if document else ''
        document_status_label=document_status_labels.get(document.get('status'),'قيد المعالجة') if document else ''
        selected_warehouse_name=next((w.get('name_ar') or w.get('name') or w.get('code','') for w in warehouses if str(w.get('id','')).replace('-','')==selected),'')
        context={'page_title':'المستندات والعمليات' if mode=='documents' else ('الأرصدة المخزنية' if mode=='balances' else 'عمليات المخازن'),'mode':mode,'base_url':base,
            'local_workspace_assets':True,
             'warehouses':warehouses,'selected_warehouse':selected,'selected_warehouse_name':selected_warehouse_name,'records':records,'document':document,
             'document_type_label':document_type_label,'document_status_label':document_status_label,'is_document_creator':bool(creator),
            'items':items,'locations':locations,'currencies':currencies,'form_lines':lines,'error':error,'report':report,
            'dispatch_lines':dispatch_lines,'destination_warehouse':request.POST.get('destination_warehouse_id') or (document.get('destination_warehouse_id') if document else ''),
            'form_reason':request.POST.get('reason') or (document.get('reason') if document else ''),
            'source_stock_status':request.POST.get('source_stock_status') or (document.get('source_stock_status') if document else ''),
            'receipt_lines':receipt_lines,'counterparty_reference':request.POST.get('counterparty_reference') or (document.get('counterparty_reference') if document else ''),
            'value_origins':value_origins,'can_correct_value':can_correct_value,
            'target_stock_status':request.POST.get('target_stock_status') or (document.get('target_stock_status') if document else ''),
            'holders':holders,'custody_origins':custody_origins,'beneficiary':beneficiary,
            'balance_preview':balance_preview,'balance_visible':balance_visible,
            'form_due_date':request.POST.get('custody_due_date') or (document.get('custody_due_date') if document else ''),
            'request_lines':request_lines,'form_type':request.POST.get('document_type') or (document['document_type'] if document else request.GET.get('document_type','RECEIPT')),
            'readiness':readiness,'draft':request.POST,'today':timezone.localdate().isoformat(),
            'form_date':request.POST.get('document_date') or (document['document_date'] if document else timezone.localdate().isoformat()),
            'posting_key':request.POST.get('posting_key') or uuid4().hex,'can_create':actions.get('create'),
            'can_approve':actions.get('approve') and document and not creator and document['status']=='SUBMITTED',
            'can_post':actions.get('post') and readiness.get('financial_ready') and document and not creator and document['status']=='APPROVED',
            'reversal_options':reversal_options,
            'lifecycle':lifecycle,'has_lifecycle_actions':any(lifecycle.values()),'decision_reason':request.POST.get('decision_reason',''),
            'can_submit':actions.get('create') and creator and document['status']=='DRAFT', 'show_editor':actions.get('create') and (not document or creator and document['status']=='DRAFT' and document['document_type']!='REVERSAL'),
            'shortcuts':shortcuts,'document_type_labels':document_type_labels,'document_status_labels':document_status_labels,
             'counts':counts,'search':search,'status_filter':status_filter,'document_type_filter':document_type_filter,
             'balance_items':balance_items,'balance_locations':balance_locations,'balance_categories':balance_categories,'balance_units':balance_units,
             'balance_search':balance_search,'balance_category':balance_category,'balance_status':balance_status,'balance_location':balance_location,
             'balance_summary':balance_summary,'balance_error':balance_error,
             'movement_items':movement_items,'movement_locations':movement_locations,'movement_units':movement_units,'movement_types':movement_types,
             'movement_search':movement_search,'movement_type':movement_type,'movement_from':movement_from,'movement_to':movement_to,
             'movement_summary':movement_summary,'movement_error':movement_error,
             'can_export_movements':can('inventory.stock.view'),
             'custody_tab':custody_tab,'custody_search':custody_search,'custody_holder':custody_holder,'custody_status':custody_status,'custody_item':custody_item,
             'custody_holders':custody_holders,'custody_items':custody_items,'custody_summary':custody_summary,'custody_error':custody_error,
             'can_custody_actions':can('inventory.documents.create'),'can_custody_documents':can('inventory.documents.view'),
             'total_documents':total_documents,'page_number':page_number,'page_count':page_count,'page_size':page_size}
        if mode=='documents' and not document and not request.GET.get('document_type'):
            return render(request,'inventory/operations_documents.html',context,status=error_status)
        return render(request,'inventory/operations.html',context,status=error_status)
    except UnauthorizedException:
        return redirect('auth:login')
    except (ValueError,TypeError):
        return HttpResponse('تحقق من معرف المخزن أو المستند',status=422)
    except ApiException as exc:
        return HttpResponse('تعذر تحميل عمليات المخازن: '+str(exc),status=403)
