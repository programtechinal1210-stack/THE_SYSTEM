"""Inventory reporting workspace composed from existing read-only inventory services."""
from datetime import timedelta
from urllib.parse import urlencode

from django.http import HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone

from shared.services.api_client import ApiException


def _date(value):
    return str(value or '')[:10]


def _in_period(value, start, end):
    day = _date(value)
    return not day or start <= day <= end


def page(request, api, identity, work, warehouses, organization, selected):
    can = lambda code: identity.get('is_admin') or code in identity.get('permissions', [])
    tab = request.GET.get('report_tab', 'overview')
    if tab not in ('overview', 'movements', 'consumption', 'control'):
        tab = 'overview'
    today = timezone.localdate()
    date_to = request.GET.get('date_to') or today.isoformat()
    date_from = request.GET.get('date_from') or (today - timedelta(days=180)).isoformat()
    category_filter = request.GET.get('category_id', '')
    errors = []
    items, categories, balances, movements, documents, reconciliation = [], [], [], [], [], {}

    def read(endpoint, params=None, default=None):
        try:
            return api.get(endpoint, params=params or {})
        except ApiException:
            errors.append(endpoint)
            return default if default is not None else {}

    if organization:
        items = read('/inventory/items', {'organization_id': organization, 'limit': 200}, {'items': []}).get('items', [])
        categories = read('/inventory/categories', {'organization_id': organization, 'limit': 200}, {'items': []}).get('items', [])
    if selected:
        balances = read('/inventory/balances', {'warehouse_id': selected}, {'items': []}).get('items', [])
        movements = read('/inventory/movements', {'warehouse_id': selected, 'skip': 0, 'limit': 200}, {'items': []}).get('items', [])
        documents = read('/inventory/documents', {'warehouse_id': selected, 'skip': 0, 'limit': 200}, {'items': []}).get('items', [])
        if can('inventory.reports.view'):
            reconciliation = read('/inventory/reports/reconciliation', {'warehouse_id': selected}, {})

    item_by_id = {str(row.get('id', '')).replace('-', ''): row for row in items}
    category_by_id = {str(row.get('id', '')).replace('-', ''): row for row in categories}
    allowed_item_ids = set(item_by_id)
    if category_filter:
        allowed_item_ids = {key for key, row in item_by_id.items()
                            if str(row.get('category_id', '')).replace('-', '') == category_filter.replace('-', '')}

    def relevant_item(row):
        return not row.get('item_id') or str(row.get('item_id')).replace('-', '') in allowed_item_ids

    movements = [row for row in movements if _in_period(row.get('posted_at'), date_from, date_to) and relevant_item(row)]
    documents = [row for row in documents if _in_period(row.get('document_date') or row.get('created_at'), date_from, date_to)]
    posted_documents = [row for row in documents if row.get('status') in ('POSTED', 'CLOSED')]
    consumption_documents = [row for row in posted_documents if row.get('document_type') == 'CONSUMPTION']
    balances = [row for row in balances if relevant_item(row)]

    # Low stock is reported only when the service supplies an explicit threshold.
    threshold_rows = [row for row in balances if row.get('reorder_point') is not None or row.get('minimum_quantity') is not None]
    low_count = None
    if threshold_rows:
        low_count = sum(float(row.get('available_to_issue') or 0) <= float(
            row.get('reorder_point') if row.get('reorder_point') is not None else row.get('minimum_quantity'))
                        for row in threshold_rows)

    def day_counts(rows, field):
        result = {}
        for row in rows:
            day = _date(row.get(field))
            if day:
                result[day] = result.get(day, 0) + 1
        return [{'label': key, 'value': value} for key, value in sorted(result.items())]

    movement_days = day_counts(movements, 'posted_at')
    incoming_days = {}
    outgoing_days = {}
    for row in movements:
        day = _date(row.get('posted_at'))
        try:
            delta = float(row.get('quantity_delta') or 0)
        except (TypeError, ValueError):
            delta = 0
        if day:
            target = incoming_days if delta > 0 else outgoing_days if delta < 0 else None
            if target is not None:
                target[day] = target.get(day, 0) + 1
    if tab == 'movements':
        labels = sorted(set(incoming_days) | set(outgoing_days))
        chart_points = [{'label': day, 'incoming': incoming_days.get(day, 0),
                         'outgoing': outgoing_days.get(day, 0)} for day in labels]
        chart_title = 'عدد قيود الوارد والصادر حسب التاريخ'
        chart_unit = 'عدد القيود المرحلة، وليس كمية مختلطة الوحدات'
    elif tab == 'consumption':
        chart_points = day_counts(consumption_documents, 'document_date')
        chart_title = 'حركات استهلاك العهد حسب التاريخ'
        chart_unit = 'عدد مستندات الاستهلاك المرحلة'
    elif tab == 'control':
        chart_points = [{'label': 'فروقات الكمية', 'value': len(reconciliation.get('quantity_differences') or [])},
                        {'label': 'فروقات القيمة', 'value': len(reconciliation.get('value_differences') or [])}]
        chart_title = 'الفروقات التي تحتاج معالجة'
        chart_unit = 'عدد الفروقات من خدمة المطابقة'
    else:
        chart_points = movement_days
        chart_title = 'اتجاه حركة المخزون خلال الفترة'
        chart_unit = 'عدد قيود دفتر الحركات المرحلة'

    balance_rows = []
    for row in balances[:100]:
        item = item_by_id.get(str(row.get('item_id', '')).replace('-', ''), {})
        balance_rows.append({
            'name': item.get('name_ar') or item.get('name') or 'صنف غير متاح',
            'code': item.get('code') or '—',
            'warehouse': next((w.get('name_ar') or w.get('name') or w.get('code') for w in warehouses
                               if str(w.get('id', '')).replace('-', '') == selected), 'المخزن الحالي'),
            'metric': 'الرصيد المتاح', 'value': row.get('available_to_issue'),
            'unit': row.get('unit_name') or row.get('unit_code') or 'الوحدة الأساسية',
            'status': row.get('reservation_status') or row.get('stock_status') or '—',
            'url': reverse('inventory:home') + '?' + urlencode({'section': 'items', 'search': item.get('code', '')}),
        })
    movement_rows = []
    for row in movements[:100]:
        item = item_by_id.get(str(row.get('item_id', '')).replace('-', ''), {})
        delta = row.get('quantity_delta') or '0'
        movement_rows.append({'name': item.get('name_ar') or item.get('name') or 'صنف غير متاح',
                              'code': item.get('code') or '—', 'warehouse': 'المخزن الحالي',
                              'metric': 'وارد' if str(delta).startswith('-') is False and float(delta or 0) > 0 else 'صادر',
                              'value': delta, 'unit': row.get('unit_name') or 'الوحدة الأساسية',
                              'status': 'مرحّل', 'url': reverse('inventory:operations') + '?' + urlencode({
                                  'mode': 'documents', 'warehouse_id': selected, 'document': row.get('posting_group_id', '')}),
                              'date': row.get('posted_at')})
    consumption_rows = [{'name': 'مستند استهلاك', 'code': row.get('document_no') or '—',
                         'warehouse': 'المخزن الحالي', 'metric': 'استهلاك مرحّل',
                         'value': row.get('line_count') or '—', 'unit': 'سجل', 'status': row.get('status'),
                         'url': reverse('inventory:operations') + '?' + urlencode({
                             'mode': 'documents', 'warehouse_id': selected, 'document': row.get('id', '')}),
                         'date': row.get('document_date')} for row in consumption_documents[:100]]
    control_rows = [{'name': 'فرق كمية', 'code': row.get('balance_id') or '—', 'warehouse': 'المخزن الحالي',
                     'metric': 'فرق جرد/مطابقة', 'value': row.get('quantity_difference'), 'unit': 'وفق سجل الرصيد',
                     'status': 'يحتاج معالجة', 'url': reverse('inventory:operations') + '?' + urlencode({
                         'mode': 'reconciliation', 'warehouse_id': selected})}
                    for row in (reconciliation.get('quantity_differences') or [])[:100]]
    table_rows = {'overview': balance_rows, 'movements': movement_rows,
                  'consumption': consumption_rows, 'control': control_rows}[tab]
    report_base = {'mode': 'reconciliation', 'warehouse_id': selected,
                   'date_from': date_from, 'date_to': date_to}
    if category_filter:
        report_base['category_id'] = category_filter
    return render(request, 'inventory/reports.html', {
        'page_title': 'التقارير والتحليلات المخزنية', 'work_context': work,
        'warehouses': warehouses, 'selected_warehouse': selected,
        'selected_warehouse_name': next((w.get('name_ar') or w.get('name') or w.get('code') for w in warehouses
                                          if str(w.get('id', '')).replace('-', '') == selected), ''),
        'report_tab': tab, 'date_from': date_from, 'date_to': date_to,
        'category_filter': category_filter, 'categories': categories,
        'summary': {'active_items': sum(bool(row.get('is_active', True)) for row in items
                                        if str(row.get('id', '')).replace('-', '') in allowed_item_ids),
                    'movement_count': len(movements), 'low_count': low_count,
                    'difference_count': len(reconciliation.get('quantity_differences') or [])},
        'low_stock_available': bool(threshold_rows), 'chart_points': chart_points,
        'chart_title': chart_title, 'chart_unit': chart_unit, 'table_rows': table_rows,
        'errors': errors, 'has_scope': bool(selected), 'can_export': can('inventory.reports.view'),
        'base_url': reverse('inventory:operations') + '?' + urlencode(report_base),
    })
