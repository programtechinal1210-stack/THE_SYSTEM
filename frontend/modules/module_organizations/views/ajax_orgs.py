from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from shared.services.api_client import ApiClient, ApiException
import json

def _get_client(request):
    client = ApiClient()
    token = request.session.get('access_token')
    if token: client._token = token
    return client

def ajax_orgs_list(request):
    client = _get_client(request)
    try:
        result = client.get('/organizations')
        orgs = result if isinstance(result, list) else result.get('items', [])
        return JsonResponse({'items': orgs, 'total': len(orgs)})
    except: return JsonResponse({'items': [], 'total': 0})

def ajax_entity_types(request):
    client = _get_client(request)
    try:
        result = client.get('/organizations/entity-types')
        types = result if isinstance(result, list) else result.get('items', [])
        return JsonResponse({'items': types})
    except: return JsonResponse({'items': []})

def ajax_org_create(request):
    if request.method != 'POST': return JsonResponse({'error': 'Method not allowed'}, status=405)
    client = _get_client(request)
    try:
        data = json.loads(request.body)
        payload = {'name': data.get('name')}
        if data.get('entity_type_id'): payload['entity_type_id'] = data['entity_type_id']
        if data.get('code'): payload['code'] = data['code']
        if data.get('contact_person'): payload['contact_person'] = data['contact_person']
        if data.get('phone'): payload['phone'] = data['phone']
        if data.get('email'): payload['email'] = data['email']
        if data.get('address'): payload['address'] = data['address']
        if 'parent_id' in data: payload['parent_id'] = data.get('parent_id') or None
        result = client.post('/organizations', payload)
        return JsonResponse({'success': True, 'id': result.get('id')})
    except ApiException as e:
        error = str(e)
        if 'duplicate' in error.lower() or 'unique' in error.lower():
            return JsonResponse({'error': 'الرمز موجود مسبقاً - استخدم رمزاً مختلفاً'}, status=400)
        return JsonResponse({'error': error}, status=400)
    
def ajax_org_update(request, org_id):
    if request.method != 'POST': return JsonResponse({'error': 'Method not allowed'}, status=405)
    client = _get_client(request)
    try:
        data = json.loads(request.body)
        payload = {}
        if data.get('name'): payload['name'] = data['name']
        if data.get('entity_type_id'): payload['entity_type_id'] = data['entity_type_id']
        if data.get('code'): payload['code'] = data['code']
        if data.get('contact_person'): payload['contact_person'] = data['contact_person']
        if data.get('phone'): payload['phone'] = data['phone']
        if data.get('email'): payload['email'] = data['email']
        if data.get('address'): payload['address'] = data['address']
        if 'parent_id' in data: payload['parent_id'] = data.get('parent_id') or None
        if 'is_active' in data: payload['is_active'] = data['is_active']
        client.put('/organizations/' + str(org_id), payload)
        return JsonResponse({'success': True})
    except ApiException as e: return JsonResponse({'error': str(e)}, status=400)

def ajax_org_delete(request, org_id):
    if request.method != 'POST': return JsonResponse({'error': 'Method not allowed'}, status=405)
    client = _get_client(request)
    try:
        client.delete('/organizations/' + str(org_id))
        return JsonResponse({'success': True})
    except ApiException as e: return JsonResponse({'error': str(e)}, status=400)
