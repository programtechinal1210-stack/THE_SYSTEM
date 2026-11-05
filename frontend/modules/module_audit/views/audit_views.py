"""
عروض سجل التدقيق
"""
from django.shortcuts import render
from django.http import JsonResponse


def list_view(request):
    """صفحة سجل التدقيق (عبر HTMX)"""
    return render(request, 'audit/index.html')


def list_api(request):
    """API - قائمة سجل التدقيق"""
    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 20))
    search = request.GET.get('search', '')
    module = request.GET.get('module', '')
    action_type = request.GET.get('action_type', '')
    severity = request.GET.get('severity', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    is_system_action = request.GET.get('is_system_action', '')

    # TODO: استدعاء AuditAPI.getLogs()
    # حالياً: بيانات وهمية
    mock_logs = [
        {'id': 1, 'actor_name': 'أحمد محمد', 'action_type': 'UPDATE', 'entity_type': 'case', 'module': 'cases', 'severity': 'info', 'changes_summary': 'تحديث حالة المعاملة', 'created_at': '2026-07-16T14:30:00'},
        {'id': 2, 'actor_name': 'سارة علي', 'action_type': 'CREATE', 'entity_type': 'user', 'module': 'users', 'severity': 'info', 'changes_summary': 'إنشاء مستخدم جديد', 'created_at': '2026-07-16T13:15:00'},
        {'id': 3, 'actor_name': 'محمد خالد', 'action_type': 'DELETE', 'entity_type': 'directive', 'module': 'execution', 'severity': 'warning', 'changes_summary': 'حذف توجيه', 'created_at': '2026-07-16T11:00:00'},
        {'id': 4, 'actor_name': 'النظام', 'action_type': 'DETECT', 'entity_type': 'anomaly', 'module': 'audit', 'severity': 'critical', 'changes_summary': 'كشف محاولة اقتحام', 'created_at': '2026-07-16T09:30:00'},
        {'id': 5, 'actor_name': 'أحمد محمد', 'action_type': 'EXPORT', 'entity_type': 'audit', 'module': 'audit', 'severity': 'info', 'changes_summary': 'تصدير سجل التدقيق', 'created_at': '2026-07-15T16:45:00'},
    ]

    # تطبيق الفلاتر (محاكاة)
    if module:
        mock_logs = [l for l in mock_logs if l['module'] == module]
    if action_type:
        mock_logs = [l for l in mock_logs if l['action_type'] == action_type]
    if severity:
        mock_logs = [l for l in mock_logs if l['severity'] == severity]
    if search:
        mock_logs = [l for l in mock_logs if search.lower() in l.get('changes_summary', '').lower() or search.lower() in l.get('actor_name', '').lower()]

    total_count = len(mock_logs)
    total_pages = max(1, (total_count + page_size - 1) // page_size)
    start = (page - 1) * page_size
    end = start + page_size
    results = mock_logs[start:end]

    data = {
        'results': results,
        'total_count': total_count,
        'current_page': page,
        'total_pages': total_pages,
        'page_start': start + 1 if results else 0,
        'page_end': min(end, total_count),
        'page_size': page_size,
    }
    return JsonResponse(data)


def detail_api(request, log_id):
    """API - تفاصيل سجل تدقيق"""
    # TODO: استدعاء AuditAPI.getLogDetail(log_id)
    log = {
        'id': log_id,
        'actor_name': 'أحمد محمد',
        'action_type': 'UPDATE',
        'entity_type': 'case',
        'module': 'cases',
        'severity': 'info',
        'changes_summary': 'تحديث حالة المعاملة من مسودة إلى قيد التنفيذ',
        'old_value': {'status': 'draft'},
        'new_value': {'status': 'in_progress'},
        'ip_address': '192.168.1.100',
        'user_agent': 'Mozilla/5.0',
        'session_id': 'abc123',
        'duration_ms': 45,
        'status_code': 200,
        'created_at': '2026-07-16T14:30:00',
    }
    return JsonResponse(log)


def detail_modal(request, log_id):
    """مودال تفاصيل سجل التدقيق"""
    # TODO: جلب البيانات من API
    context = {
        'log': {
            'id': log_id,
            'actor_name': 'أحمد محمد',
            'action_type': 'UPDATE',
            'entity_type': 'case',
            'module': 'cases',
            'severity': 'info',
            'changes_summary': 'تحديث حالة المعاملة',
            'created_at': '2026-07-16T14:30:00',
        }
    }
    return render(request, 'audit/modals/_audit_detail_modal.html', context)
