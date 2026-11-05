from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from shared.services.api_client import ApiClient, ApiException

def ajax_users_delete(request, user_id):
    if request.method != 'DELETE':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    client = ApiClient()
    token = request.session.get('access_token')
    if token: client._token = token

    try:
        client.delete('/users/' + str(user_id))
        return JsonResponse({'success': True})
    except ApiException as e:
        return JsonResponse({'error': str(e)}, status=400)
