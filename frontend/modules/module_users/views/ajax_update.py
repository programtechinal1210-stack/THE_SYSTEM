from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from shared.services.api_client import ApiClient, ApiException
import json

def ajax_users_update(request, user_id):
    if request.method != 'PUT':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    client = ApiClient()
    token = request.session.get('access_token')
    if token: client._token = token

    try:
        data = json.loads(request.body)
        role = data.pop('role', None)
        client.put('/users/' + str(user_id), data)
        if role:
            client.post('/users/' + str(user_id) + '/roles', {'role_name': role})
        return JsonResponse({'success': True})
    except ApiException as e:
        return JsonResponse({'error': str(e)}, status=400)
