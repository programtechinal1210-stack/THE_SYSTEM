# modules/module_users/views/ajax_status.py
from django.http import JsonResponse
from shared.services.api_client import ApiClient, ApiException

def ajax_update_status(request, user_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'طريقة غير مسموح بها'}, status=405)

    client = ApiClient()
    is_active = request.POST.get('is_active') == 'true'

    try:
        client.put(f'/users/{user_id}', {'is_active': is_active})
        return JsonResponse({
            'success': True,
            'user_id': str(user_id),
            'is_active': is_active
        })
    except ApiException as e:
        return JsonResponse({'error': str(e)}, status=400)

