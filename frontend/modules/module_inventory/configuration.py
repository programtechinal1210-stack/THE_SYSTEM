"""Inventory settings center adapter; persistence remains in Core/inventory APIs."""
from uuid import UUID

from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from shared.services.api_client import ApiClient, ApiException, UnauthorizedException

TABS = {'general', 'operations', 'alerts', 'integrations'}


@require_http_methods(['GET', 'POST'])
def page(request):
    api = ApiClient(token=request.session.get('access_token'))
    error, history = '', []
    tab = request.GET.get('tab', 'general')
    if tab not in TABS:
        tab = 'general'
    try:
        identity = api.get('/auth/me')
        can = lambda permission: identity.get('is_admin') or permission in identity.get('permissions', [])
        if not (can('core.legal_entities.view') or can('inventory.warehouses.view')):
            return HttpResponse('لا تملك صلاحية عرض إعدادات المخازن', status=403)
        if request.method == 'POST':
            if not can('core.legal_entities.manage'):
                return HttpResponse('لا تملك صلاحية إدارة إعدادات الملكية', status=403)
            command = request.POST.get('command')
            identifier = UUID(request.POST['legal_entity_id']).hex if command != 'create' else ''
            if command == 'create':
                api.post('/legal-entities', {'code': request.POST.get('code', ''), 'name': request.POST.get('name', ''), 'valuation_currency': request.POST.get('valuation_currency') or None})
            elif command == 'approve':
                api.post('/legal-entities/' + identifier + '/approve', {})
            elif command == 'link':
                api.post('/legal-entities/' + identifier + '/organizations', {'organization_id': UUID(request.POST['organization_id']).hex})
            elif command == 'warehouse':
                api.put('/inventory/warehouses/' + UUID(request.POST['warehouse_id']).hex + '/owner', {'legal_entity_id': identifier})
            elif command == 'controls':
                api.put('/inventory/financial-controls/' + identifier, {'posting_enabled': request.POST.get('posting_enabled') == 'on', 'closed_through': request.POST.get('closed_through') or None})
            elif command == 'currency':
                api.put('/legal-entities/' + identifier, {'code': request.POST.get('code', ''), 'name': request.POST.get('name', ''), 'valuation_currency': request.POST.get('valuation_currency') or None})
            else:
                return HttpResponse('إجراء غير صالح', status=422)
            target_tab = 'operations' if command == 'controls' else 'integrations' if command == 'link' else 'general'
            return HttpResponseRedirect(reverse('inventory:configuration') + '?tab=' + target_tab)
    except UnauthorizedException:
        return redirect('auth:login')
    except (ApiException, ValueError, KeyError) as exc:
        error = str(exc) or 'تعذر حفظ إعدادات المخازن'
    try:
        context = api.get('/profile/work-context')
        entities = api.get('/legal-entities') if can('core.legal_entities.view') else {'items': [], 'links': []}
        currencies = api.get('/currency/currencies') if can('core.currency.view') else []
        warehouses = []
        if can('inventory.warehouses.view') and context.get('selected_id'):
            warehouses = api.get('/inventory/warehouses', params={'organization_id': context['selected_id'], 'limit': 200}).get('items', [])
            for warehouse in warehouses:
                warehouse['readiness'] = api.get('/inventory/warehouses/' + warehouse['id'] + '/readiness')
        can_audit = can('core.settings.audit.view')
        if can_audit:
            history = api.get('/settings-center/changes', params={'search': 'inventory', 'skip': 0}).get('items', [])[:5]
    except UnauthorizedException:
        return redirect('auth:login')
    except ApiException:
        return HttpResponse('تعذر تحميل إعدادات المخازن', status=503)
    selected_name = context.get('selected_name')
    if not selected_name:
        selected_name = next((item.get('name') for item in context.get('items', [])
                              if str(item.get('id')) == str(context.get('selected_id'))), None)
    return render(request, 'inventory/configuration.html', {
        'page_title': 'إعدادات إدارة المخازن', 'error': error,
        'legal_entities': entities.get('items', []), 'links': entities.get('links', []), 'currencies': currencies,
        'organizations': context.get('items', []), 'warehouses': warehouses, 'can_manage': can('core.legal_entities.manage'),
        'draft': request.POST, 'setup_required': entities.get('setup_required', False), 'tab': tab,
        'can_audit': can('core.settings.audit.view'), 'history': history,
        'current_organization': selected_name or context.get('selected_id'),
    })
