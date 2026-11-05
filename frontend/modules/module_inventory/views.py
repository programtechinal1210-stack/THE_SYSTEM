"""Inventory master data over the shared API transport; no database writes."""
from decimal import Decimal, InvalidOperation
from uuid import UUID
from urllib.parse import urlencode

from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from shared.services.api_client import ApiClient, ApiException, UnauthorizedException

SECTIONS = {'items': 'الأصناف', 'categories': 'التصنيفات', 'units': 'وحدات القياس',
            'warehouses': 'المخازن', 'locations': 'مواقع التخزين'}


def permission(section, action):
    return f'inventory.{"warehouses" if section == "locations" else section}.{action}'


def allowed(identity, code):
    return identity.get('is_admin') or code in identity.get('permissions', [])


def identifier(value):
    return UUID(str(value)).hex


def stocktakes_center(request, client, identity):
    """Read-only stocktake workspace over the certified stocktake API."""
    can = lambda code: allowed(identity, code)
    errors = {}
    try:
        work_context = client.get('/profile/work-context')
    except UnauthorizedException:
        return redirect('auth:login')
    except ApiException:
        return HttpResponse('تعذر تحميل جهة العمل الحالية.', status=503)

    organization_id = ''
    try:
        if work_context.get('selected_id'):
            organization_id = identifier(work_context['selected_id'])
    except (ValueError, TypeError):
        errors['work_context'] = 'تعذر تحديد جهة العمل الحالية.'

    warehouses = []
    if organization_id and can('inventory.warehouses.view'):
        try:
            result = client.get('/inventory/warehouses', params={
                'organization_id': organization_id, 'limit': 200,
            })
            warehouses = [{**row, 'id': identifier(row['id'])}
                          for row in result.get('items', [])]
        except ApiException:
            errors['warehouses'] = 'تعذر تحميل المخازن المصرح بها.'

    warehouse_ids = {row['id'] for row in warehouses}
    requested_warehouse = request.GET.get('warehouse_id', '')
    try:
        selected_warehouse = (identifier(requested_warehouse) if requested_warehouse
                              else (warehouses[0]['id'] if warehouses else ''))
    except (ValueError, TypeError):
        return HttpResponse('تحقق من المخزن المختار', status=422)
    if requested_warehouse and selected_warehouse not in warehouse_ids:
        return HttpResponse('المخزن غير متاح ضمن جهة العمل الحالية', status=403)

    selected_warehouse_name = next(
        (row.get('name_ar') or row.get('name') or row.get('code', '')
         for row in warehouses if row['id'] == selected_warehouse), '')
    form_error = ''
    show_create_form = request.GET.get('create') == '1'
    if request.method == 'POST' and selected_warehouse:
        action = request.POST.get('action', '')
        try:
            if action == 'create' and can('inventory.stocktakes.create'):
                created = client.post('/inventory/stocktakes', {
                    'warehouse_id': selected_warehouse,
                    'count_type': request.POST.get('count_type', 'FULL'),
                    'all_locations': True,
                    'item_ids': [], 'stock_status': None,
                    'reason': request.POST.get('reason', '').strip(),
                })
                return HttpResponseRedirect(request.path + '?' + urlencode({
                    'section': 'stocktakes', 'warehouse_id': selected_warehouse,
                    'stocktake': identifier(created['id']),
                }))
            if action in ('submit', 'approve', 'reopen', 'cancel', 'confirm-empty'):
                stocktake_id = identifier(request.POST.get('stocktake_id'))
                client.post('/inventory/stocktakes/' + stocktake_id + '/' + action,
                            {'reason': request.POST.get('reason', '').strip()})
                return HttpResponseRedirect(request.path + '?' + urlencode({
                    'section': 'stocktakes', 'warehouse_id': selected_warehouse,
                    'stocktake': stocktake_id,
                }))
        except (ApiException, ValueError, TypeError) as exc:
            form_error = str(exc) or 'تعذر تنفيذ الإجراء. تحقق من الصلاحية وحالة الجرد.'
            show_create_form = action == 'create'
    tab = request.GET.get('tab', 'active')
    if tab not in ('active', 'review', 'settlements', 'history'):
        tab = 'active'
    stocktake_status = request.GET.get('status', '')
    count_type = request.GET.get('count_type', '')
    search = request.GET.get('search', '').strip()
    try:
        skip = max(0, int(request.GET.get('skip', 0)))
    except (ValueError, TypeError):
        skip = 0

    status_labels = {
        'OPEN': 'قيد العد', 'SUBMITTED': 'بانتظار المراجعة',
        'APPROVED': 'فروقات تحتاج معالجة', 'SETTLED': 'مكتمل ومرحّل',
        'CANCELLED': 'ملغى',
    }
    type_labels = {
        'FULL': 'شامل', 'PARTIAL': 'جزئي', 'CYCLE': 'دوري',
        'SURPRISE': 'انتقائي', 'CONTINUOUS': 'مستمر',
    }
    rows = []
    settlements = []
    detail = None
    detail_actions = {}
    if selected_warehouse and can('inventory.stocktakes.view'):
        try:
            result = client.get('/inventory/stocktakes', params={
                'warehouse_id': selected_warehouse, 'skip': 0, 'limit': 200,
            })
            source_rows = result.get('items', [])
            for raw in source_rows:
                row = dict(raw)
                row['id'] = identifier(row['id'])
                row['status_label'] = status_labels.get(row.get('status'), 'غير معروف')
                row['count_type_label'] = type_labels.get(row.get('count_type'), row.get('count_type') or '—')
                row['warehouse_name'] = selected_warehouse_name or 'المخزن المحدد'
                creator = str(row.get('created_by') or '')
                row['responsible_label'] = ('المسؤول · ' + creator.replace('-', '')[-8:]) if creator else 'غير متاح'
                row['detail_url'] = request.path + '?' + urlencode({
                    'section': 'stocktakes', 'warehouse_id': selected_warehouse,
                    'stocktake': row['id'], 'tab': tab,
                })
                try:
                    info = client.get('/inventory/stocktakes/' + row['id'])
                    total = int(info.get('total_lines') or 0)
                    uncounted = int(info.get('uncounted_lines') or 0)
                    row['total_lines'] = total
                    row['uncounted_lines'] = uncounted
                    row['progress'] = (round((total - uncounted) * 100 / total)
                                       if total else 0)
                    row['difference_count'] = sum(
                        1 for line in info.get('lines', [])
                        if line.get('difference') not in (None, '', '0', '0.0', '0.00')
                    ) if info.get('book_visible') else 0
                except ApiException:
                    row['total_lines'] = row['uncounted_lines'] = None
                    row['progress'] = None
                    row['difference_count'] = 0
                try:
                    actions = client.get('/inventory/stocktakes/' + row['id'] + '/actions')
                except ApiException:
                    actions = {}
                row['actions'] = actions
                if actions.get('count'):
                    row['next_action'] = 'متابعة العد'
                elif actions.get('submit'):
                    row['next_action'] = 'إرسال للمراجعة'
                elif actions.get('approve'):
                    row['next_action'] = 'مراجعة النتائج'
                elif actions.get('settle'):
                    row['next_action'] = 'إنشاء التسوية'
                elif row.get('status') == 'SETTLED':
                    row['next_action'] = 'عرض النتائج'
                else:
                    row['next_action'] = 'عرض التفاصيل'
                row['main_action_url'] = row['detail_url']
                rows.append(row)
            try:
                docs = client.get('/inventory/documents', params={
                    'warehouse_id': selected_warehouse, 'skip': 0, 'limit': 200,
                }).get('items', [])
                settlements = [doc for doc in docs if
                               doc.get('document_type') == 'ADJUSTMENT' and
                               doc.get('adjustment_kind') == 'COUNT']
            except ApiException:
                errors['settlements'] = 'تعذر تحميل مستندات التسوية.'
        except ApiException:
            errors['stocktakes'] = 'تعذر تحميل عمليات الجرد. حاول تحديث الصفحة.'

    requested_detail = request.GET.get('stocktake', '')
    if requested_detail and selected_warehouse and requested_detail in {row['id'] for row in rows}:
        try:
            detail = client.get('/inventory/stocktakes/' + requested_detail)
            detail_actions = client.get('/inventory/stocktakes/' + requested_detail + '/actions')
        except ApiException:
            errors['detail'] = 'تعذر تحميل تفاصيل عملية الجرد.'

    def visible(row):
        if stocktake_status and row.get('status') != stocktake_status:
            return False
        if count_type and row.get('count_type') != count_type:
            return False
        if search.casefold() not in ' '.join(str(row.get(key, '')) for key in (
                'count_no', 'warehouse_name', 'responsible_label')).casefold():
            return False
        if tab == 'active':
            return row.get('status') in ('OPEN', 'SUBMITTED', 'APPROVED')
        if tab == 'review':
            return row.get('status') in ('SUBMITTED', 'APPROVED') or row.get('difference_count', 0) > 0
        if tab == 'settlements':
            return row.get('status') == 'SETTLED' or any(
                str(doc.get('stocktake_id') or '').replace('-', '') == row['id']
                for doc in settlements)
        return True

    filtered_rows = [row for row in rows if visible(row)]
    page_rows = filtered_rows[skip:skip + 25]
    summary = {
        'ongoing': sum(row.get('status') == 'OPEN' for row in rows),
        'review': sum(row.get('status') == 'SUBMITTED' for row in rows),
        'differences': sum(row.get('difference_count', 0) for row in rows),
        'settled': sum(row.get('status') == 'SETTLED' for row in rows),
    }
    query_base = {'section': 'stocktakes', 'warehouse_id': selected_warehouse,
                  'tab': tab}
    if search: query_base['search'] = search
    if stocktake_status: query_base['status'] = stocktake_status
    if count_type: query_base['count_type'] = count_type
    reset_url = request.path + '?' + urlencode({'section': 'stocktakes', 'warehouse_id': selected_warehouse})
    return render(request, 'inventory/stocktakes.html', {
        'page_title': 'الجرد والتسويات المخزنية', 'work_context': work_context,
        'selected_organization_name': next((row.get('name', '') for row in work_context.get('items', [])
                                            if str(row.get('id', '')).replace('-', '') == organization_id), ''),
        'organization_selected': bool(organization_id), 'warehouses': warehouses,
        'selected_warehouse': selected_warehouse, 'selected_warehouse_name': selected_warehouse_name,
        'can_create': can('inventory.stocktakes.create') and bool(selected_warehouse),
        'rows': page_rows, 'filtered_count': len(filtered_rows), 'total_count': len(rows),
        'summary': summary, 'settlements': settlements, 'tab': tab, 'search': search,
        'status_filter': stocktake_status, 'count_type_filter': count_type,
        'status_options': list(status_labels.items()), 'count_type_options': list(type_labels.items()),
        'detail': detail, 'detail_actions': detail_actions, 'errors': errors,
        'form_error': form_error, 'show_create_form': show_create_form,
        'reset_url': reset_url, 'new_url': request.path + '?' + urlencode({
            'section': 'stocktakes', 'warehouse_id': selected_warehouse, 'create': '1'}),
        'query_base': urlencode(query_base), 'has_previous': skip > 0,
        'has_next': skip + 25 < len(filtered_rows), 'previous_url': request.path + '?' + urlencode({**query_base, 'skip': max(0, skip - 25)}),
        'next_url': request.path + '?' + urlencode({**query_base, 'skip': skip + 25}),
    })


@require_http_methods(['GET', 'POST'])
def stocktake_execution(request, client, identity):
    """Fast count-entry workspace backed by the stocktake line API."""
    if not allowed(identity, 'inventory.stocktakes.count'):
        return HttpResponse('لا تملك صلاحية تسجيل العد الفعلي', status=403)
    stocktake_id = request.GET.get('stocktake', '')
    try:
        stocktake_id = identifier(stocktake_id)
    except (ValueError, TypeError):
        return HttpResponse('عملية الجرد المحددة غير صالحة', status=422)

    api_error = ''
    try:
        detail = client.get('/inventory/stocktakes/' + stocktake_id)
        actions = client.get('/inventory/stocktakes/' + stocktake_id + '/actions')
        if request.method == 'POST':
            action = request.POST.get('action', '')
            if action == 'count':
                line_id = identifier(request.POST.get('line_id'))
                client.put('/inventory/stocktakes/' + stocktake_id + '/lines/' + line_id, {
                    'quantity': request.POST.get('quantity', ''),
                    'recount': request.POST.get('recount') == 'on',
                    'reason': request.POST.get('reason', '').strip() or None,
                })
                next_line = line_id
                if request.POST.get('next') == '1':
                    refreshed = client.get('/inventory/stocktakes/' + stocktake_id)
                    next_line = next((str(row['id']).replace('-', '') for row in refreshed.get('lines', [])
                                      if row.get('counted_quantity') is None and row.get('recount_quantity') is None), line_id)
                return HttpResponseRedirect(request.path + '?section=stocktakes&mode=count&stocktake=' + stocktake_id + '&line=' + next_line)
            if action == 'submit':
                client.post('/inventory/stocktakes/' + stocktake_id + '/submit', {'reason': request.POST.get('reason', '').strip()})
                return HttpResponseRedirect(request.path + '?section=stocktakes&mode=count&stocktake=' + stocktake_id)
    except UnauthorizedException:
        return redirect('auth:login')
    except (ApiException, ValueError, TypeError) as exc:
        api_error = str(exc) or 'تعذر حفظ العد. تحقق من الكمية وحالة الجرد.'
        try:
            detail = client.get('/inventory/stocktakes/' + stocktake_id)
            actions = client.get('/inventory/stocktakes/' + stocktake_id + '/actions')
        except ApiException:
            return HttpResponse('تعذر تحميل عملية الجرد', status=503)

    lines = []
    for line in detail.get('lines', []):
        row = dict(line)
        row['id'] = identifier(row['id'])
        final = row.get('recount_quantity') if row.get('recount_quantity') is not None else row.get('counted_quantity')
        row['count_state'] = 'counted' if final is not None else 'uncounted'
        row['count_state_label'] = 'تم العد' if final is not None else 'غير معدود'
        row['input_value'] = '' if final is None else final
        row['location_label'] = row.get('location_name') or 'دون موقع محدد'
        row['unit_label'] = row.get('unit_name') or 'الوحدة الأساسية'
        lines.append(row)
    selected_line_id = request.GET.get('line', '')
    selected = next((row for row in lines if row['id'] == selected_line_id), None)
    if selected is None:
        selected = next((row for row in lines if row['count_state'] == 'uncounted'), None) or (lines[0] if lines else None)
    total = detail.get('total_lines')
    uncounted = detail.get('uncounted_lines')
    counted = (int(total) - int(uncounted)) if total is not None and uncounted is not None else sum(row['count_state'] == 'counted' for row in lines)
    progress = round(counted * 100 / int(total)) if total else 0
    return render(request, 'inventory/stocktake_execution.html', {
        'page_title': 'تنفيذ الجرد وتسجيل العد الفعلي', 'detail': detail, 'actions': actions,
        'lines': lines, 'selected': selected, 'selected_line_id': selected['id'] if selected else '',
        'counted': counted, 'uncounted': int(uncounted) if uncounted is not None else len(lines) - counted,
        'total': int(total) if total is not None else len(lines), 'progress': progress,
        'api_error': api_error, 'execution_url': request.path + '?section=stocktakes&mode=count&stocktake=' + stocktake_id,
        'center_url': request.path + '?section=stocktakes&stocktake=' + stocktake_id,
        'can_submit': bool(actions.get('submit')),
    })


@require_http_methods(['GET', 'POST'])
def stocktake_review(request, client, identity):
    """Review saved count results using the certified stocktake contracts."""
    if not allowed(identity, 'inventory.stocktakes.view'):
        return HttpResponse('لا تملك صلاحية مراجعة فروقات الجرد', status=403)
    stocktake_id = request.GET.get('stocktake', '')
    try:
        stocktake_id = identifier(stocktake_id)
    except (ValueError, TypeError):
        return HttpResponse('عملية الجرد المحددة غير صالحة', status=422)

    api_error = ''
    try:
        if request.method == 'POST':
            action = request.POST.get('action', '')
            if action in ('approve', 'reopen'):
                client.post('/inventory/stocktakes/' + stocktake_id + '/' + action, {
                    'reason': request.POST.get('reason', '').strip(),
                })
                return HttpResponseRedirect(request.path + '?' + urlencode({
                    'section': 'stocktakes', 'mode': 'review', 'stocktake': stocktake_id,
                }))
        detail = client.get('/inventory/stocktakes/' + stocktake_id)
        actions = client.get('/inventory/stocktakes/' + stocktake_id + '/actions')
    except UnauthorizedException:
        return redirect('auth:login')
    except (ApiException, ValueError, TypeError) as exc:
        api_error = str(exc) or 'تعذر تحميل نتائج الجرد أو تنفيذ الإجراء.'
        try:
            detail = client.get('/inventory/stocktakes/' + stocktake_id)
            actions = client.get('/inventory/stocktakes/' + stocktake_id + '/actions')
        except ApiException:
            return HttpResponse('تعذر تحميل نتائج الجرد', status=503)

    selected_filter = request.GET.get('filter', 'all')
    if selected_filter not in ('all', 'shortage', 'surplus', 'matched'):
        selected_filter = 'all'
    search = request.GET.get('search', '').strip().lower()
    rows = []
    counted_total = shortage_total = surplus_total = matched_total = 0
    for raw in detail.get('lines', []):
        row = dict(raw)
        row['id'] = identifier(row['id'])
        final = row.get('recount_quantity') if row.get('recount_quantity') is not None else row.get('counted_quantity')
        row['final_quantity'] = final
        row['unit_label'] = row.get('unit_name') or 'الوحدة الأساسية'
        row['location_label'] = row.get('location_name') or 'دون موقع محدد'
        row['item_label'] = row.get('item_name') or row.get('item_code') or 'صنف غير مسمى'
        row['item_code_label'] = row.get('item_code') or '—'
        row['counted_label'] = 'غير معدود' if final is None else f'{final} {row["unit_label"]}'
        difference = row.get('difference')
        row['variance_visible'] = difference is not None
        row['variance_kind'] = 'uncounted'
        row['variance_label'] = 'غير معدود'
        row['difference_label'] = '—'
        if difference is not None:
            try:
                value = Decimal(str(difference))
            except (InvalidOperation, ValueError, TypeError):
                value = None
            if value is not None:
                row['difference_label'] = f'{difference} {row["unit_label"]}'
                if value < 0:
                    row['variance_kind'], row['variance_label'] = 'shortage', 'عجز'
                    shortage_total += 1
                elif value > 0:
                    row['variance_kind'], row['variance_label'] = 'surplus', 'زيادة'
                    surplus_total += 1
                else:
                    row['variance_kind'], row['variance_label'] = 'matched', 'مطابق'
                    matched_total += 1
        if final is not None:
            counted_total += 1
        haystack = f'{row["item_label"]} {row["item_code_label"]}'.lower()
        if search and search not in haystack:
            continue
        if selected_filter != 'all' and row['variance_kind'] != selected_filter:
            continue
        row['primary_action'] = 'عرض التفاصيل'
        if actions.get('approve') and row['variance_kind'] in ('shortage', 'surplus', 'matched'):
            row['primary_action'] = 'اعتماد نتائج الجرد'
        elif actions.get('reopen'):
            row['primary_action'] = 'إعادة فتح الجرد للعد'
        rows.append(row)

    selected_id = request.GET.get('line', '')
    selected = next((row for row in rows if row['id'] == selected_id), None)
    if selected is None and rows:
        selected = rows[0]
    total_lines = detail.get('total_lines')
    try:
        total_lines = int(total_lines) if total_lines is not None else len(detail.get('lines', []))
    except (TypeError, ValueError):
        total_lines = len(detail.get('lines', []))
    return render(request, 'inventory/stocktake_review.html', {
        'detail': detail, 'actions': actions, 'rows': rows, 'selected': selected,
        'selected_filter': selected_filter, 'search': request.GET.get('search', ''),
        'counted_total': counted_total, 'shortage_total': shortage_total,
        'surplus_total': surplus_total, 'matched_total': matched_total,
        'total_lines': total_lines, 'api_error': api_error,
        'review_url': request.path + '?section=stocktakes&mode=review&stocktake=' + stocktake_id,
        'center_url': request.path + '?section=stocktakes&stocktake=' + stocktake_id,
        'execution_url': request.path + '?section=stocktakes&mode=count&stocktake=' + stocktake_id,
        'can_count': bool(actions.get('count')),
        'variance_visible': any(row.get('variance_visible') for row in rows),
    })


def dashboard(request, client, identity):
    can = lambda code: allowed(identity, code)
    work_context = {}
    errors = {key: '' for key in (
        'work_context', 'warehouses', 'documents', 'document_actions',
        'requests', 'custody', 'readiness',
    )}

    try:
        work_context = client.get('/profile/work-context')
    except UnauthorizedException:
        return redirect('auth:login')
    except ApiException:
        errors['work_context'] = 'تعذر تحميل جهة العمل الحالية.'

    organization_id = ''
    if work_context.get('selected_id'):
        try:
            organization_id = identifier(work_context['selected_id'])
        except (ValueError, TypeError):
            errors['work_context'] = 'تعذر تحديد جهة العمل الحالية.'

    def load(key, endpoint, params=None):
        try:
            return client.get(endpoint, params=params)
        except UnauthorizedException:
            raise
        except ApiException:
            errors[key] = 'تعذر تحميل البيانات. حاول تحديث الصفحة.'
            return None

    warehouses = []
    if organization_id and can('inventory.warehouses.view'):
        result = load('warehouses', '/inventory/warehouses',
                      {'organization_id': organization_id, 'limit': 200})
        if result is not None:
            warehouses = [
                {**row, 'id': identifier(row['id'])}
                for row in result.get('items', [])
            ]

    warehouse_ids = {identifier(row['id']) for row in warehouses}
    requested_warehouse = request.GET.get('warehouse_id')
    try:
        selected_warehouse = (identifier(requested_warehouse) if requested_warehouse else
                              (identifier(warehouses[0]['id']) if warehouses else ''))
    except (ValueError, TypeError):
        return HttpResponse('تحقق من المخزن المختار', status=422)
    if requested_warehouse and selected_warehouse not in warehouse_ids:
        return HttpResponse('المخزن غير متاح ضمن جهة العمل الحالية', status=403)

    selected_warehouse_name = next(
        (row.get('name_ar') or row.get('name') or row.get('code', '')
         for row in warehouses if identifier(row['id']) == selected_warehouse),
        '',
    )
    documents = []
    requests = []
    custody = []
    selected_scope_available = bool(organization_id and selected_warehouse)
    can_open_documents = (can('inventory.documents.view') and
                          can('inventory.warehouses.view'))
    can_open_custody = (can('inventory.stock.view') and
                        can('inventory.warehouses.view'))

    if selected_scope_available and can_open_documents:
        result = load('documents', '/inventory/documents',
                      {'warehouse_id': selected_warehouse, 'limit': 10})
        if result is not None:
            documents = result.get('items', [])
    if organization_id and can('inventory.requests.view') and can('inventory.requests.approve'):
        result = load('requests', '/inventory/requests',
                      {'organization_id': organization_id, 'skip': 0, 'limit': 50})
        if result is not None:
            requests = result.get('items', [])
    if selected_scope_available and can_open_custody:
        result = load('custody', '/inventory/custody',
                      {'warehouse_id': selected_warehouse, 'skip': 0, 'limit': 50})
        if result is not None:
            custody = result.get('items', [])

    actor = str(identity.get('id', '')).replace('-', '')
    action_candidates = any(
        (row.get('status') == 'SUBMITTED' and can('inventory.documents.approve')) or
        (row.get('status') == 'APPROVED' and can('inventory.documents.post'))
        for row in documents
    )
    document_actions = None
    if selected_scope_available and can_open_documents and action_candidates:
        document_actions = load(
            'document_actions',
            '/inventory/document-actions',
            {'warehouse_id': selected_warehouse},
        )
    ready_to_post = False
    if (selected_scope_available and document_actions and document_actions.get('post') and
            any(row.get('status') == 'APPROVED' for row in documents)):
        readiness = load(
            'readiness',
            '/inventory/warehouses/' + selected_warehouse + '/readiness',
        )
        ready_to_post = bool(readiness and readiness.get('financial_ready'))
    operation_url = reverse('inventory:operations')
    stocktakes_url = reverse('inventory:home') + '?' + urlencode({
        'section': 'stocktakes',
        **({'warehouse_id': selected_warehouse} if selected_warehouse else {}),
    })
    if selected_warehouse:
        document_list_url = operation_url + '?' + urlencode({
            'mode': 'documents', 'warehouse_id': selected_warehouse,
        })
        custody_url = reverse('inventory:custody') + '?' + urlencode({
            'warehouse_id': selected_warehouse,
        })
    else:
        document_list_url = operation_url + '?mode=documents'
        custody_url = reverse('inventory:custody')

    type_labels = {
        'RECEIPT': 'استلام', 'ISSUE_DIRECT': 'صرف', 'ISSUE_CUSTODY': 'تسليم عهدة',
        'TRANSFER_DIRECT': 'تحويل', 'TRANSFER_DISPATCH': 'إرسال تحويل',
        'TRANSFER_RECEIPT': 'استلام تحويل', 'RETURN_INTERNAL': 'مرتجع داخلي',
        'RETURN_SUPPLIER': 'مرتجع مورد', 'CONSUMPTION': 'استهلاك عهدة',
        'ADJUSTMENT': 'تسوية', 'STATUS_CHANGE': 'تغيير حالة',
        'SCRAP': 'إتلاف', 'REVERSAL': 'عكس مستند', 'LOSS_TRANSIT': 'فقد أثناء النقل',
    }
    status_labels = {
        'DRAFT': 'مسودة', 'SUBMITTED': 'بانتظار الاعتماد', 'APPROVED': 'معتمد',
        'POSTED': 'مرحّل', 'CLOSED': 'مغلق', 'REJECTED': 'مرفوض',
        'CANCELLED': 'ملغى',
    }
    recent_documents = []
    tasks = []
    for row in documents:
        document_url = document_list_url + '&document=' + identifier(row['id'])
        recent_documents.append({
            'number': row.get('document_no', ''),
            'type': type_labels.get(row.get('document_type'), 'عملية مخزنية'),
            'date': row.get('document_date', ''),
            'status': status_labels.get(row.get('status'), 'قيد المعالجة'),
            'url': document_url,
        })
        if str(row.get('created_by') or '').replace('-', '') == actor:
            continue
        if (row.get('status') == 'SUBMITTED' and document_actions and
                document_actions.get('approve')):
            tasks.append({
                'label': 'مستند بانتظار اعتمادك',
                'detail': row.get('document_no', ''),
                'url': document_url,
                'tone': 'blue',
            })
        elif (row.get('status') == 'APPROVED' and ready_to_post):
            tasks.append({
                'label': 'مستند معتمد بانتظار الترحيل',
                'detail': row.get('document_no', ''),
                'url': document_url,
                'tone': 'violet',
            })

    for row in requests:
        if (row.get('status') == 'SUBMITTED' and
                str(row.get('created_by') or '').replace('-', '') != actor):
            tasks.append({
                'label': 'طلب مواد بانتظار اعتمادك',
                'detail': row.get('request_no', ''),
                'url': reverse('inventory:requests') + '?' + urlencode({'request': row['id']}),
                'tone': 'blue',
            })

    overdue_custody = [row for row in custody if row.get('overdue')]
    if overdue_custody:
        tasks.append({
            'label': 'عهدة متأخرة تحتاج إلى متابعة',
            'detail': overdue_custody[0].get('item_name', ''),
            'url': custody_url,
            'tone': 'teal',
        })

    cards = [
        {
            'key': 'documents', 'title': 'المستندات والعمليات',
            'description': 'الاستلام والصرف والتحويل والمرتجعات',
            'icon': 'document', 'tone': 'orange',
            'href': document_list_url,
            'available': can_open_documents,
        },
        {
            'key': 'items', 'title': 'دليل الأصناف والمواد',
            'description': 'إدارة الأصناف والتصنيفات ووحدات القياس',
            'icon': 'box', 'tone': 'teal',
            'href': reverse('inventory:home') + '?section=items',
            'available': can('inventory.items.view'),
        },
        {
            'key': 'warehouses', 'title': 'إدارة المخازن',
            'description': 'استعراض المخازن ومواقع التخزين',
            'icon': 'warehouse', 'tone': 'blue',
            'href': reverse('inventory:home') + '?section=warehouses',
            'available': can('inventory.warehouses.view'),
        },
        {
            'key': 'requests', 'title': 'طلبات المواد',
            'description': 'إنشاء الطلبات ومتابعة اعتمادها وتنفيذها',
            'icon': 'clipboard', 'tone': 'violet',
            'href': reverse('inventory:requests'),
            'available': can('inventory.requests.view'),
        },
        {
            'key': 'settings', 'title': 'إعدادات المخازن',
            'description': 'ملكية المخزون وجاهزية الترحيل',
            'icon': 'settings', 'tone': 'slate',
            'href': reverse('inventory:configuration'),
            'available': can('inventory.warehouses.view') or
                         can('core.legal_entities.view'),
        },
        {
            'key': 'reports', 'title': 'الأرصدة والتقارير',
            'description': 'التقارير والتحليلات والمطابقة المخزنية',
            'icon': 'chart', 'tone': 'violet',
            'href': operation_url + '?' + urlencode({
                'mode': 'reconciliation' if can('inventory.reports.view') else 'balances',
                **({'warehouse_id': selected_warehouse} if selected_warehouse else {}),
            }),
            'available': can('inventory.warehouses.view') and
                         (can('inventory.reports.view') or can('inventory.stock.view')),
        },
        {
            'key': 'stocktakes', 'title': 'الجرد والتسويات',
            'description': 'متابعة العد والفروقات والتسويات الرسمية',
            'icon': 'checklist', 'tone': 'red',
            'href': stocktakes_url,
            'available': can('inventory.stocktakes.view'),
        },
        {
            'key': 'custody', 'title': 'العهدة والاستهلاك',
            'description': 'متابعة المواد المسلّمة والمستهلكة والمتبقية',
            'icon': 'person', 'tone': 'teal',
            'href': custody_url,
            'available': can_open_custody,
        },
    ]
    cards = [card for card in cards if card['available']]
    recent_documents = recent_documents[:5]
    return render(request, 'inventory/home.html', {
        'page_title': 'إدارة المخازن والمواد',
        'work_context': work_context,
        'selected_organization_name': next(
            (row.get('name', '') for row in work_context.get('items', [])
             if str(row.get('id', '')).replace('-', '') == organization_id),
            '',
        ),
        'organization_selected': bool(organization_id),
        'cards': cards,
        'warehouses': warehouses,
        'selected_warehouse': selected_warehouse,
        'selected_warehouse_name': selected_warehouse_name,
        'can_select_warehouse': bool(warehouses),
        'can_recent_documents': can_open_documents,
        'can_recent_requests': (can('inventory.requests.view') and
                                can('inventory.requests.approve')),
        'can_recent_custody': can_open_custody,
        'has_document_scope': selected_scope_available,
        'has_request_scope': bool(organization_id),
        'has_custody_scope': selected_scope_available,
        'recent_documents': recent_documents,
        'tasks': tasks[:6],
        'overdue_custody': overdue_custody[:3],
        'document_list_url': document_list_url,
        'custody_url': custody_url,
        'errors': errors,
    })


@require_http_methods(['GET', 'POST'])
def home(request):
    client = ApiClient(token=request.session.get('access_token'))
    try:
        identity = client.get('/auth/me')
    except UnauthorizedException:
        return redirect('auth:login')
    except ApiException:
        return HttpResponse('تعذر التحقق من الهوية', status=503)
    if request.GET.get('section') == 'stocktakes':
        if not allowed(identity, 'inventory.stocktakes.view'):
            return HttpResponse('ليس لديك صلاحية عرض عمليات الجرد', status=403)
        if request.GET.get('mode') == 'count':
            return stocktake_execution(request, client, identity)
        if request.GET.get('mode') == 'review':
            return stocktake_review(request, client, identity)
        return stocktakes_center(request, client, identity)
    if request.method == 'GET' and 'section' not in request.GET:
        return dashboard(request, client, identity)
    section = request.GET.get('section', 'items')
    if section not in SECTIONS:
        return HttpResponse('القسم غير موجود', status=404)
    if not allowed(identity, permission(section, 'view')):
        return HttpResponse('ليس لديك صلاحية عرض هذا القسم', status=403)
    try:
        selected = client.get('/profile/work-context') if not request.GET.get('organization_id') else {}
        org = identifier(request.GET.get('organization_id') or selected.get('selected_id') or identity.get('organization_id'))
        warehouse = identifier(request.GET['warehouse_id']) if request.GET.get('warehouse_id') else ''
        editing = identifier(request.GET['edit']) if request.GET.get('edit') else ''
        skip = max(0, int(request.GET.get('skip', 0)))
    except (ValueError, TypeError, AttributeError):
        return HttpResponse('تحقق من المؤسسة أو المخزن أو الصفحة المختارة', status=422)
    search = request.GET.get('search', '').strip()
    location_type_filter = request.GET.get('location_type', '')
    category_filter = ''
    active_filter = request.GET.get('is_active', '')
    item_type_filter = request.GET.get('item_type', '')
    item_types = {
        'MATERIAL': 'مادة', 'SPARE_PART': 'قطعة غيار', 'CONSUMABLE': 'مستهلك',
        'TOOL': 'أداة', 'OTHER': 'أخرى',
    }
    if section == 'items':
        try:
            category_filter = identifier(request.GET['category_id']) if request.GET.get('category_id') else ''
        except (ValueError, TypeError):
            return HttpResponse('تحقق من التصنيف المختار', status=422)
        if active_filter not in ('', 'true', 'false'):
            return HttpResponse('تحقق من حالة التفعيل المختارة', status=422)
        if item_type_filter and item_type_filter not in item_types:
            return HttpResponse('تحقق من نوع الصنف المختار', status=422)
    if section == 'locations' and not warehouse:
        return HttpResponseRedirect(reverse('inventory:home') + '?section=warehouses')
    endpoint = f'/inventory/warehouses/{warehouse}/locations' if section == 'locations' else '/inventory/' + section
    query = {'section': section, 'organization_id': org}
    if warehouse:
        query['warehouse_id'] = warehouse
    if search:
        query['search'] = search
    if section == 'items':
        if category_filter:
            query['category_id'] = category_filter
        if active_filter:
            query['is_active'] = active_filter
        if item_type_filter:
            query['item_type'] = item_type_filter
    base_url = reverse('inventory:home') + '?' + urlencode(query)
    error = ''
    can_manage = allowed(identity, permission(section, 'manage'))
    can_view_categories = allowed(identity, permission('categories', 'view'))
    can_view_units = allowed(identity, permission('units', 'view'))
    show_item_form = section in ('items', 'warehouses') and can_manage and bool(
        editing or request.GET.get('create') == '1' or request.method == 'POST'
    )
    submitted = request.POST if request.method == 'POST' else {}
    fields = [
        ('code', 'رمز الصنف' if section == 'items' else 'الرمز', True),
        ('name_ar' if section in ('items', 'categories') else 'name',
         'اسم الصنف' if section == 'items' else 'الاسم', True),
    ]
    if section == 'units':
        fields += [('dimension', 'البعد (مثل length أو mass)', False), ('precision', 'عدد المنازل العشرية (0–6)', True)]
    if section == 'items':
        fields += [('category_id', 'التصنيف', False), ('base_unit_id', 'الوحدة الأساسية', False),
                   ('attributes_json', 'المواصفات بصيغة JSON', False),('aliases_json','المرادفات (قائمة JSON)',False),
                   ('barcode','الباركود',False),('item_type','نوع الصنف',True),('notes','ملاحظات',False)]
    if section in ('items','categories','units','locations'):
        fields += [('is_active','حالة التفعيل',True)]
    if section == 'locations':
        fields += [('location_type', 'نوع الموقع', True)]
    if section in ('categories', 'warehouses', 'locations'):
        fields += [('parent_id', 'الأصل', False)]
    if section == 'warehouses':
        fields += [('warehouse_type', 'نوع المخزن', True),
                   ('operating_department_id', 'الإدارة المشغلة', False),
                   ('manager_user_id', 'المستخدم المسؤول', False), ('status', 'الحالة', True)]
    visible_fields = [
        (name, label, required) for name, label, required in fields
        if not (section == 'items' and (
            (name == 'category_id' and not can_view_categories) or
            (name == 'base_unit_id' and not can_view_units)
        ))
    ]
    current = {}
    try:
        if editing:
            if section == 'locations':
                current = next((row for row in client.get(endpoint)['items'] if row['id'] == editing), None)
                if current is None:
                    return HttpResponse('الموقع غير متاح', status=404)
            else:
                current = client.get(endpoint + '/' + editing)
        if request.method == 'POST':
            if not can_manage:
                return HttpResponse('ليس لديك صلاحية التعديل', status=403)
            action = request.POST.get('action', '')
            if action == 'delete' and editing:
                client.delete(endpoint + '/' + editing)
            elif action == 'save':
                data = {name: request.POST.get(name, '') for name, _, _ in visible_fields}
                for name in ('category_id', 'base_unit_id', 'parent_id', 'operating_department_id', 'manager_user_id'):
                    if name in data:
                        data[name] = identifier(data[name]) if data[name] else None
                if section not in ('units', 'locations'):
                    data['organization_id'] = org
                if section == 'units':
                    data['precision'] = int(data['precision'])
                if section == 'items':
                    data['attributes_json'] = data['attributes_json'] or '{}'
                    data['aliases_json'] = data['aliases_json'] or '[]'
                    data['barcode'] = data['barcode'] or None
                    data['item_type'] = data['item_type'] or 'MATERIAL'
                if 'is_active' in data:
                    data['is_active']=request.POST.get('is_active',str(current.get('is_active',1)))=='1'
                if editing:
                    client.put(endpoint + '/' + editing, data)
                else:
                    client.post(endpoint, data)
            else:
                return HttpResponse('إجراء غير صالح', status=422)
            return HttpResponseRedirect(base_url)
    except UnauthorizedException:
        return redirect('auth:login')
    except (ApiException, ValueError, TypeError) as exc:
        error = str(exc) or 'تعذر حفظ البيانات؛ تحقق من الحقول'
    try:
        params = {'organization_id': org, 'search': search, 'skip': skip, 'limit': 50}
        if section == 'items':
            if category_filter:
                params['category_id'] = category_filter
            if active_filter:
                params['is_active'] = active_filter
            if item_type_filter:
                params['item_type'] = item_type_filter
        records = client.get(endpoint, params=None if section == 'locations' else params)['items']
        all_location_records = list(records) if section == 'locations' else []
        if section == 'locations':
            if location_type_filter:
                records = [row for row in records if row.get('location_type') == location_type_filter]
            if active_filter in ('true', 'false'):
                records = [row for row in records if bool(row.get('is_active')) == (active_filter == 'true')]
            if search:
                needle = search.casefold()
                records = [row for row in records if needle in str(row.get('code', '')).casefold()
                           or needle in str(row.get('name', '')).casefold()]
        options = {}
        for target, field, may_view in (
            ('categories', 'category_id', can_view_categories),
            ('units', 'base_unit_id', can_view_units),
        ):
            if section == 'items' and may_view:
                options[field] = client.get('/inventory/' + target, params={'organization_id': org, 'limit': 200})['items']
                for option in options[field]:
                    option['id'] = identifier(option['id'])
        if section in ('categories', 'warehouses', 'locations'):
            options['parent_id'] = [row for row in records if row['id'] != editing]
    except UnauthorizedException:
        return redirect('auth:login')
    except ApiException:
        return HttpResponse('تعذر تحميل بيانات المخازن', status=503)
    category_labels = {
        identifier(row['id']): row.get('name_ar') or row.get('name') or row.get('code', '')
        for row in options.get('category_id', [])
    }
    unit_labels = {
        identifier(row['id']): row.get('name') or row.get('code', '')
        for row in options.get('base_unit_id', [])
    }
    type_labels = item_types
    for row in records:
        row['category_label'] = category_labels.get(identifier(row['category_id']), '') if row.get('category_id') else ''
        row['unit_label'] = unit_labels.get(identifier(row['base_unit_id']), '') if row.get('base_unit_id') else ''
        row['type_label'] = type_labels.get(row.get('item_type'), 'غير محدد')
        row['status_label'] = 'نشط' if row.get('is_active') else 'معطل'
        row['warehouse_type_label'] = {
            'central': 'رئيسي', 'branch': 'فرعي', 'independent': 'مستقل',
        }.get(row.get('warehouse_type'), row.get('warehouse_type') or '—')
        if section == 'locations':
            row['location_type'] = {
                'zone': 'منطقة', 'aisle': 'ممر', 'shelf': 'رف', 'bin': 'حاوية',
                'yard': 'ساحة', 'cold': 'تبريد',
            }.get(row.get('location_type'), row.get('location_type') or '—')
        row.setdefault('operating_department', row.get('operating_department_name') or '')
        row['edit_url'] = base_url + '&edit=' + row['id']
        row['label'] = row.get('name_ar') or row.get('name')
        row['locations_url'] = reverse('inventory:home') + '?' + urlencode({
            'section': 'locations', 'organization_id': org, 'warehouse_id': row['id']})
    prepared_fields = []
    for name, label, required in visible_fields:
        defaults = {'precision': '3', 'status': 'active', 'warehouse_type': 'central', 'location_type': 'shelf', 'attributes_json': '{}',
                    'aliases_json': '[]', 'item_type': 'MATERIAL', 'is_active': '1'}
        value = submitted.get(name, current.get(name, defaults.get(name, '')))
        choices = [{'value': '', 'label': '—'}] + [
            {'value': item['id'], 'label': item.get('name_ar') or item.get('name') or item['code']}
            for item in options.get(name, [])
        ] if name in options else []
        if name == 'status':
            choices = [{'value': status, 'label': label} for status, label in (
                ('active', 'نشط'), ('suspended', 'موقوف'), ('closed', 'مغلق'),
            )]
        if name == 'is_active':
            value = str(int(value)) if isinstance(value, (int, bool)) else value
            choices = [{'value': '1', 'label': 'نشط'}, {'value': '0', 'label': 'معطل'}]
        if name == 'item_type':
            choices = [{'value': kind, 'label': label} for kind, label in item_types.items()]
        if name == 'warehouse_type':
            choices = [{'value': value, 'label': label} for value, label in (
                ('central', 'رئيسي'), ('branch', 'فرعي'), ('independent', 'مستقل'),
            )]
        if name == 'location_type':
            choices = [{'value': value, 'label': label} for value, label in (
                ('zone', 'منطقة'), ('aisle', 'ممر'), ('shelf', 'رف'),
                ('bin', 'حاوية'), ('yard', 'ساحة'), ('cold', 'تبريد'),
            )]
        prepared_fields.append({
            'name': name, 'label': label, 'required': required, 'value': value,
            'options': choices, 'type': 'number' if name == 'precision' else 'text',
        })
    if section == 'locations':
        try:
            warehouse_record = client.get('/inventory/warehouses/' + warehouse)
        except UnauthorizedException:
            return redirect('auth:login')
        except ApiException:
            return HttpResponse('تعذر تحميل تفاصيل المخزن', status=503)
        tab = request.GET.get('tab', 'locations')
        if tab not in ('locations', 'overview', 'balances', 'movements', 'stocktakes'):
            tab = 'locations'
        operational_data = []
        tab_error = ''
        endpoint_by_tab = {
            'balances': ('/inventory/balances', 'inventory.stock.view'),
            'movements': ('/inventory/movements', 'inventory.stock.view'),
            'stocktakes': ('/inventory/stocktakes', 'inventory.stocktakes.view'),
        }
        if tab in endpoint_by_tab:
            api_endpoint, required_permission = endpoint_by_tab[tab]
            if not allowed(identity, required_permission):
                tab_error = 'لا تتوفر صلاحية عرض هذا القسم.'
            else:
                try:
                    operational_data = client.get(api_endpoint, params={'warehouse_id': warehouse}).get('items', [])
                    for row in operational_data:
                        for key in ('item_name', 'document_no', 'count_no', 'item_id',
                                    'location_name', 'location_id', 'document_id',
                                    'on_hand', 'quantity', 'status', 'document_date',
                                    'count_date', 'created_at'):
                            row.setdefault(key, '')
                except (ApiException, KeyError, TypeError):
                    tab_error = 'تعذر تحميل بيانات هذا القسم. حاول تحديث الصفحة.'
        location_base = reverse('inventory:home') + '?' + urlencode({
            'section': 'locations', 'organization_id': org, 'warehouse_id': warehouse,
        })
        return render(request, 'inventory/warehouse_detail.html', {
            'page_title': warehouse_record.get('name', 'تفاصيل المخزن'),
            'warehouse': warehouse_record,
            'warehouse_type_label': {'central': 'رئيسي', 'branch': 'فرعي', 'independent': 'مستقل'}.get(warehouse_record.get('warehouse_type'), '—'),
            'warehouse_status_label': {'active': 'نشط', 'suspended': 'موقوف', 'closed': 'مغلق'}.get(warehouse_record.get('status'), '—'),
            'locations': records, 'location_count': len(all_location_records),
            'location_type_filter': location_type_filter, 'active_filter': active_filter,
            'search': search, 'tab': tab, 'tab_error': tab_error,
            'operational_data': operational_data, 'can_manage': can_manage,
            'can_view_balances': allowed(identity, 'inventory.stock.view'),
            'can_view_movements': allowed(identity, 'inventory.stock.view'),
            'can_view_stocktakes': allowed(identity, 'inventory.stocktakes.view'),
            'show_item_form': show_item_form, 'editing': editing,
            'form': {'action': 'save', 'fields': prepared_fields, 'submit': 'حفظ الموقع'},
            'location_base': location_base,
            'warehouse_list_url': reverse('inventory:home') + '?' + urlencode({'section': 'warehouses', 'organization_id': org}),
            'locations_url': location_base,
        })
    return render(request, 'inventory/catalog.html', {
        'page_title': 'دليل الأصناف والمواد' if section == 'items' else SECTIONS[section],
        'section': section, 'records': records,
        'navigation': [{'label': title, 'url': reverse('inventory:home') + '?' + urlencode({'section': key, 'organization_id': org})}
                       for key,title in SECTIONS.items() if key != 'locations' and allowed(identity, permission(key, 'view'))],
        'error': error, 'editing': editing, 'can_manage': can_manage, 'base_url': base_url,
        'show_item_form': show_item_form,
        'form': {'action': 'save', 'fields': prepared_fields, 'submit': 'حفظ البيانات'},
        'search': search, 'organization_id': org,
        'reset_url': reverse('inventory:home') + '?' + urlencode({
            'section': section, 'organization_id': org,
        }),
        'category_filter': category_filter, 'active_filter': active_filter,
        'item_type_filter': item_type_filter, 'item_types': list(item_types.items()),
        'categories': options.get('category_id', []),
        'previous_url': base_url + '&' + urlencode({'skip': max(0, skip-50)}),
        'next_url': base_url + '&' + urlencode({'skip': skip+50}),
        'has_previous': skip > 0, 'has_next': len(records) == 50 and section != 'locations',
    })
