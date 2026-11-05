"""
عروض التصدير
"""
from django.shortcuts import render
from django.http import JsonResponse, FileResponse
from django.views.decorators.http import require_http_methods
import os


def list_view(request):
    """صفحة التصدير"""
    return render(request, 'audit/index.html')


def list_api(request):
    """API - قائمة التصدير"""
    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 20))
    export_type = request.GET.get('export_type', '')
    entity_type = request.GET.get('entity_type', '')
    status = request.GET.get('status', '')

    # TODO: استدعاء ExportService
    mock_data = [
        {
            'id': 'ex1',
            'export_name': 'تقرير التدقيق يوليو 2026',
            'export_type': 'pdf',
            'entity_type': 'audit',
            'record_count': 1284,
            'file_size_bytes': 2516582,
            'file_path': '/exports/audit-2026-07.pdf',
            'status': 'completed',
            'duration_seconds': 45,
            'created_at': '2026-07-15T10:00:00',
            'completed_at': '2026-07-15T10:00:45',
        },
        {
            'id': 'ex2',
            'export_name': 'متابعات الفترة',
            'export_type': 'excel',
            'entity_type': 'followup',
            'record_count': 45,
            'file_size_bytes': 876544,
            'file_path': None,
            'status': 'processing',
            'duration_seconds': None,
            'created_at': '2026-07-14T08:00:00',
            'completed_at': None,
        },
    ]

    # تطبيق الفلاتر
    if export_type:
        mock_data = [e for e in mock_data if e['export_type'] == export_type]
    if entity_type:
        mock_data = [e for e in mock_data if e['entity_type'] == entity_type]
    if status:
        mock_data = [e for e in mock_data if e['status'] == status]

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
    """API - تفاصيل تصدير"""
    return JsonResponse({'id': id, 'status': 'success'})


@require_http_methods(['POST'])
def create_api(request):
    """API - إنشاء تصدير جديد"""
    return JsonResponse({'status': 'success', 'message': 'جاري تجهيز التصدير...', 'export_id': 'ex-new'}, status=201)


def download_api(request, id):
    """API - تحميل ملف التصدير"""
    # TODO: جلب مسار الملف من قاعدة البيانات
    file_path = f'/exports/audit-export-{id}.pdf'
    if os.path.exists(file_path):
        return FileResponse(open(file_path, 'rb'), as_attachment=True, filename=f'export-{id}.pdf')
    return JsonResponse({'error': 'الملف غير موجود'}, status=404)


@require_http_methods(['DELETE'])
def delete_api(request, id):
    """API - حذف تصدير"""
    return JsonResponse({'status': 'success', 'message': 'تم حذف التصدير'}, status=204)


def add_modal(request):
    """مودال تصدير جديد"""
    from django.utils import timezone
    context = {'today': timezone.now().date()}
    return render(request, 'audit/modals/_export_modal.html', context)
