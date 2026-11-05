"""
عروض سجل التنفيذ
"""
from django.shortcuts import render
from django.http import JsonResponse


def list_view(request):
    """صفحة سجل التنفيذ"""
    return render(request, 'audit/index.html')


def list_api(request):
    """API - قائمة سجل التنفيذ"""
    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 20))
    entity_type = request.GET.get('entity_type', '')
    execution_type = request.GET.get('execution_type', '')
    is_delayed = request.GET.get('is_delayed', '')

    # TODO: استدعاء ExecutionService
    mock_data = [
        {'id': 'e1', 'entity_type': 'directive', 'entity_id': 'ت-045-2026', 'action': 'CREATED', 'actor_name': 'أحمد محمد', 'notes': 'إنشاء توجيه جديد', 'duration_seconds': 2, 'is_delayed': False, 'created_at': '2026-07-16T14:30:00'},
        {'id': 'e2', 'entity_type': 'task', 'entity_id': 'م-001-2026', 'action': 'COMPLETED', 'actor_name': 'سارة علي', 'notes': 'إكمال المهمة بنجاح', 'duration_seconds': 4, 'is_delayed': False, 'created_at': '2026-07-16T13:15:00'},
        {'id': 'e3', 'entity_type': 'action', 'entity_id': 'إ-002-2026', 'action': 'UPDATED', 'actor_name': 'محمد خالد', 'notes': 'تحديث نسبة التقدم', 'duration_seconds': 1, 'is_delayed': True, 'delay_reason': 'تأخر في استلام البيانات', 'created_at': '2026-07-16T11:00:00'},
    ]

    # تطبيق الفلاتر
    if entity_type:
        mock_data = [e for e in mock_data if e['entity_type'] == entity_type]
    if execution_type:
        mock_data = [e for e in mock_data if e['action'] == execution_type]
    if is_delayed == 'true':
        mock_data = [e for e in mock_data if e['is_delayed']]
    elif is_delayed == 'false':
        mock_data = [e for e in mock_data if not e['is_delayed']]

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
    """API - تفاصيل سجل تنفيذ"""
    return JsonResponse({'id': id, 'status': 'success'})
