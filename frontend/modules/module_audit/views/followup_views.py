"""
عروض المتابعات
"""
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods


def list_view(request):
    """صفحة المتابعات"""
    return render(request, 'audit/index.html')


def list_api(request):
    """API - قائمة المتابعات"""
    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 20))

    # TODO: استدعاء FollowupService
    mock_data = [
        {'id': 'f1', 'entity_type': 'directive', 'entity_id': 'ت-045-2026', 'notes': 'متابعة تنفيذ التوجيه', 'category': 'URGENT', 'progress_percentage': 65, 'is_escalated': False, 'is_overdue': False, 'due_date': '2026-07-25', 'resolved_at': None},
        {'id': 'f2', 'entity_type': 'task', 'entity_id': 'م-001-2026', 'notes': 'جمع البيانات المالية', 'category': 'GENERAL', 'progress_percentage': 80, 'is_escalated': False, 'is_overdue': False, 'due_date': '2026-07-20', 'resolved_at': None},
        {'id': 'f3', 'entity_type': 'action', 'entity_id': 'إ-002-2026', 'notes': 'مراجعة الفواتير', 'category': 'REVIEW', 'progress_percentage': 100, 'is_escalated': False, 'is_overdue': False, 'due_date': '2026-07-15', 'resolved_at': '2026-07-15T12:00:00'},
    ]

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


@require_http_methods(['POST'])
def create_api(request):
    """API - إنشاء متابعة"""
    # TODO: استدعاء FollowupService.create()
    return JsonResponse({'status': 'success', 'message': 'تم إنشاء المتابعة بنجاح'}, status=201)


def detail_api(request, id):
    """API - تفاصيل متابعة"""
    # TODO: استدعاء FollowupService.get()
    return JsonResponse({'id': id, 'status': 'success'})


@require_http_methods(['PUT', 'PATCH'])
def update_api(request, id):
    """API - تحديث متابعة"""
    return JsonResponse({'status': 'success', 'message': 'تم تحديث المتابعة'})


@require_http_methods(['POST'])
def resolve_api(request, id):
    """API - إكمال متابعة"""
    return JsonResponse({'status': 'success', 'message': 'تم إكمال المتابعة'})


@require_http_methods(['POST'])
def escalate_api(request, id):
    """API - تصعيد متابعة"""
    return JsonResponse({'status': 'success', 'message': 'تم تصعيد المتابعة'})


@require_http_methods(['DELETE'])
def delete_api(request, id):
    """API - حذف متابعة"""
    return JsonResponse({'status': 'success', 'message': 'تم حذف المتابعة'}, status=204)


def add_modal(request):
    """مودال إضافة متابعة"""
    return render(request, 'audit/modals/_followup_add_modal.html')


def edit_modal(request, id):
    """مودال تعديل متابعة"""
    context = {
        'followup': {
            'id': id,
            'notes': 'متابعة قيد التنفيذ',
            'category': 'GENERAL',
            'progress_percentage': 50,
            'priority_score': 70,
            'due_date': '2026-07-30',
        }
    }
    return render(request, 'audit/modals/_followup_edit_modal.html', context)


def detail_modal(request, id):
    """مودال تفاصيل متابعة"""
    context = {
        'followup': {
            'id': id,
            'notes': 'متابعة تنفيذ التوجيه',
            'category': 'URGENT',
            'progress_percentage': 65,
            'is_escalated': False,
            'due_date': '2026-07-25',
            'created_at': '2026-07-16T10:00:00',
        }
    }
    return render(request, 'audit/modals/_followup_detail_modal.html', context)
