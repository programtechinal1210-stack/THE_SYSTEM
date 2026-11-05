from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from modules.module_settings.services.settings_service import settings_service
from shared.services.api_client import ApiException
from modules.module_notifications.views.core_views import failure

@require_GET
def get_notifications_api(request):
    try:
        return JsonResponse({'success': True, 'notifications': settings_service.get_notifications(int(request.GET.get('limit',20)))})
    except ValueError:
        return JsonResponse({'success': False, 'error': 'Invalid limit'}, status=400)
    except ApiException as exc: return failure(exc)

@require_GET
def get_unread_count_api(request):
    try: return JsonResponse(settings_service.get_unread_count())
    except ApiException as exc: return failure(exc)

@require_POST
def mark_read_api(request, notification_id):
    try:
        settings_service.mark_read(notification_id)
        return JsonResponse({'success': True})
    except ApiException as exc: return failure(exc)

@require_POST
def mark_all_read_api(request):
    try:
        settings_service.mark_all_read()
        return JsonResponse({'success': True})
    except ApiException as exc: return failure(exc)

@require_GET
def get_notification_types_api(request):
    try: return JsonResponse({'success': True, 'types': settings_service.get_notification_settings()})
    except ApiException as exc: return failure(exc)

@require_GET
def get_users_api(request):
    try: return JsonResponse({'success': True, 'users': settings_service.client.get('/users/')})
    except ApiException as exc: return failure(exc)
