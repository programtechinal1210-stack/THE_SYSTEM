from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from shared.services.api_client import ApiClient, ApiException
import json

def _get_client(request):
    client = ApiClient()
    token = request.session.get('access_token')
    if token:
        client._token = token
    return client

def ajax_entity_type_create(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    client = _get_client(request)
    try:
        data = json.loads(request.body)
        payload = {
            'code': data.get('code', '').upper(),
            'name': data.get('name'),
            'description': data.get('description', ''),
            'is_active': data.get('is_active', True)
        }
        result = client.post('/organizations/entity-types', payload)
        return JsonResponse({'success': True, 'id': result.get('id')})
    except ApiException as e:
        error = str(e)
        if 'duplicate' in error.lower() or 'unique' in error.lower():
            return JsonResponse({'error': 'الكود موجود مسبقاً - استخدم كوداً مختلفاً'}, status=400)
        return JsonResponse({'error': error}, status=400)

def ajax_entity_type_update(request, type_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    client = _get_client(request)
    try:
        data = json.loads(request.body)
        payload = {}
        if data.get('code'): payload['code'] = data['code'].upper()
        if data.get('name'): payload['name'] = data['name']
        if data.get('description') is not None: payload['description'] = data['description']
        if 'is_active' in data: payload['is_active'] = data['is_active']
        client.put('/organizations/entity-types/' + str(type_id), payload)
        return JsonResponse({'success': True})
    except ApiException as e:
        return JsonResponse({'error': str(e)}, status=400)

def ajax_entity_type_delete(request, type_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    client = _get_client(request)
    try:
        client.delete('/organizations/entity-types/' + str(type_id))
        return JsonResponse({'success': True})
    except ApiException as e:
        return JsonResponse({'error': str(e)}, status=400)
