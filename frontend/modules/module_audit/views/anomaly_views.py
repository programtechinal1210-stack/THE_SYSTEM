"""
عروض الحالات الشاذة
"""
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods


def list_view(request):
    """صفحة الحالات الشاذة"""
    return render(request, 'audit/index.html')


def list_api(request):
    """API - قائمة الحالات الشاذة"""
    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 20))
    anomaly_type = request.GET.get('anomaly_type', '')
    severity = request.GET.get('severity', '')
    resolution_status = request.GET.get('resolution_status', '')

    # TODO: استدعاء AnomalyService
    mock_data = [
        {
            'id': 'a1',
            'anomaly_type_code': 'brute_force_attempt',
            'title': 'محاولة اقتحام محتملة',
            'description': 'رصد 5 محاولات دخول فاشلة من IP 192.168.1.100 خلال 10 دقائق',
            'severity': 'critical',
            'resolution_status': 'open',
            'related_user_name': 'أحمد محمد',
            'related_ip': '192.168.1.100',
            'evidence': {'attempts': 5, 'time_window': '10 دقائق'},
            'detected_at': '2026-07-16T09:30:00',
        },
        {
            'id': 'a2',
            'anomaly_type_code': 'off_hours_activity',
            'title': 'نشاط خارج أوقات العمل',
            'description': 'نشاط غير عادي في الساعة 2 صباحاً - تحديث صلاحيات',
            'severity': 'warning',
            'resolution_status': 'investigating',
            'related_user_name': 'محمد خالد',
            'related_ip': '192.168.1.50',
            'evidence': {'time': '02:00', 'action': 'تحديث صلاحيات'},
            'detected_at': '2026-07-15T02:00:00',
        },
    ]

    # تطبيق الفلاتر
    if anomaly_type:
        mock_data = [a for a in mock_data if a['anomaly_type_code'] == anomaly_type]
    if severity:
        mock_data = [a for a in mock_data if a['severity'] == severity]
    if resolution_status:
        mock_data = [a for a in mock_data if a['resolution_status'] == resolution_status]

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
    """API - تفاصيل حالة شاذة"""
    return JsonResponse({'id': id, 'status': 'success'})


@require_http_methods(['POST'])
def investigate_api(request, id):
    """API - بدء تحقيق في حالة شاذة"""
    return JsonResponse({'status': 'success', 'message': 'تم بدء التحقيق'})


@require_http_methods(['POST'])
def resolve_api(request, id):
    """API - حل حالة شاذة"""
    return JsonResponse({'status': 'success', 'message': 'تم حل الحالة الشاذة'})
