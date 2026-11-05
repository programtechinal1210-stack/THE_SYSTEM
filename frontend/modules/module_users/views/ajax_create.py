from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from shared.services.api_client import ApiClient, ApiException
import json, re

def ajax_users_create(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    client = ApiClient()
    token = request.session.get('access_token')
    if token: client._token = token

    try:
        data = json.loads(request.body)
        role = data.pop('role', None)

        # إذا لم يكن UUID صالحاً، احذفه
        org = data.get('organization_id', '')
        uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        if not org or not re.match(uuid_pattern, org, re.I):
            data.pop('organization_id', None)

        data['role_names'] = [role] if role else []
        result = client.post('/auth/register', data)
        user_id = result.get('id')

        return JsonResponse({'success': True, 'id': user_id})
    except (ApiException, ValueError) as e:
        return JsonResponse({'error': str(e)}, status=400)
