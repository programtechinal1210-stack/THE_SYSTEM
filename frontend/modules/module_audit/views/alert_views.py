"""
عروض التنبيهات
"""
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods


def list_view(request):
    """صفحة التنبيهات"""
    return render(request, 'audit/index.html')


def list_api(request):
    """API - قائمة التنبيهات"""
    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 20))
    module = request.GET.get('module', '')
    severity_threshold = request.GET.get('severity_threshold', '')
    is_active = request.GET.get('is_active', '')

    # TODO: استدعاء AlertService
    mock_data = [
        {
            'id': 'al1',
            'name': 'تنبيه محاولات الدخول الفاشلة',
            'description': 'تنبيه عند رصد 5 محاولات دخول فاشلة خلال 10 دقائق',
            'module': 'users',
            'action_type': 'LOGIN',
            'severity_threshold': 'critical',
            'cooldown_minutes': 60,
            'notify_channels': ['in_app', 'email'],
            'is_active': True,
            'last_triggered_at': '2026-07-16T09:30:00',
            'trigger_count': 3,
            'created_at': '2026-07-10T08:00:00',
        },
        {
            'id': 'al2',
            'name': 'تنبيه الحذف الجماعي',
            'description': 'تنبيه عند حذف أكثر من 10 سجلات دفعة واحدة',
            'module': 'cases',
            'action_type': 'DELETE',
            'severity_threshold': 'warning',
            'cooldown_minutes': 30,
            'notify_channels': ['in_app'],
            'is_active': True,
            'last_triggered_at': None,
            'trigger_count': 0,
            'created_at': '2026-07-08T10:00:00',
        },
    ]

    # تطبيق الفلاتر
    if module:
        mock_data = [a for a in mock_data if a['module'] == module]
    if severity_threshold:
        mock_data = [a for a in mock_data if a['severity_threshold'] == severity_threshold]
    if is_active == 'true':
        mock_data = [a for a in mock_data if a['is_active']]
    elif is_active == 'false':
        mock_data = [a for a in mock_data if not a['is_active']]

    total_count = len(mock_data)
    total_pages = max(1, (total_count + page_size - 1) // page_size)
    start = (page - 1) * page_size
    results = mock_data[start:start + page_size]

    return JsonResponse({
        'results': results,
        'total_count': total_count,
        'current_page': page,
        'total_pages': total_pages,
        'page_start': start + 1 if results else 0,
        'page_end': min(start + page_size, total_count),
    })


def detail_api(request, id):
    """API - تفاصيل تنبيه"""
    return JsonResponse({'id': id, 'status': 'success'})


@require_http_methods(['POST'])
def create_api(request):
    """API - إنشاء تنبيه"""
    return JsonResponse({'status': 'success', 'message': 'تم إنشاء التنبيه'}, status=201)


@require_http_methods(['PUT', 'PATCH'])
def update_api(request, id):
    """API - تحديث تنبيه"""
    return JsonResponse({'status': 'success', 'message': 'تم تحديث التنبيه'})


@require_http_methods(['POST'])
def toggle_api(request, id):
    """API - تبديل حالة التنبيه (نشط/غير نشط)"""
    return JsonResponse({'status': 'success', 'message': 'تم تبديل حالة التنبيه'})


@require_http_methods(['DELETE'])
def delete_api(request, id):
    """API - حذف تنبيه"""
    return JsonResponse({'status': 'success', 'message': 'تم حذف التنبيه'}, status=204)


def add_modal(request):
    """مودال إضافة تنبيه"""
    return render(request, 'audit/modals/_alert_add_modal.html')


def edit_modal(request, id):
    """مودال تعديل تنبيه"""
    context = {
        'alert': {
            'id': id,
            'name': 'تنبيه محاولات الدخول',
            'description': 'وصف التنبيه',
            'module': 'users',
            'severity_threshold': 'warning',
            'cooldown_minutes': 60,
        }
    }
    return render(request, 'audit/modals/_alert_edit_modal.html', context)
