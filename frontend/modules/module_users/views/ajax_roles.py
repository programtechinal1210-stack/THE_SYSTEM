from django.http import JsonResponse
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt
from shared.services.api_client import ApiClient, ApiException

def _get_client(request):
    client = ApiClient()
    token = request.session.get('access_token')
    if token: client._token = token
    return client

# ========== الأدوار ==========
def ajax_role_create(request):
    if request.method != 'POST': return JsonResponse({'error': 'Method not allowed'}, status=405)
    client = _get_client(request)
    try:
        data = {'name': request.POST.get('name'), 'description': request.POST.get('description', '')}
        client.post('/roles/', data)
        return redirect('users:roles')
    except ApiException as e: return JsonResponse({'error': str(e)}, status=400)

def ajax_role_update(request, role_id):
    if request.method != 'POST': return JsonResponse({'error': 'Method not allowed'}, status=405)
    client = _get_client(request)
    try:
        data = {'name': request.POST.get('name'), 'description': request.POST.get('description', '')}
        client.put('/roles/' + str(role_id), data)
        return redirect('users:roles')
    except ApiException as e: return JsonResponse({'error': str(e)}, status=400)

def ajax_role_delete(request, role_id):
    if request.method != 'POST': return JsonResponse({'error': 'Method not allowed'}, status=405)
    client = _get_client(request)
    try:
        client.delete('/roles/' + str(role_id))
        return redirect('users:roles')
    except ApiException as e: return redirect('users:roles')

# ========== الصلاحيات ==========
def ajax_permission_create(request):
    if request.method != 'POST': return JsonResponse({'error': 'Method not allowed'}, status=405)
    client = _get_client(request)
    try:
        data = {
            'code': request.POST.get('code'),
            'name': request.POST.get('name'),
            'system': request.POST.get('system', 'goms'),
            'resource': request.POST.get('resource', ''),
            'action': request.POST.get('action', ''),
        }
        client.post('/permissions/', data)
        return redirect('users:roles')
    except ApiException as e: return JsonResponse({'error': str(e)}, status=400)

def ajax_permission_update(request, perm_id):
    if request.method != 'POST': return JsonResponse({'error': 'Method not allowed'}, status=405)
    client = _get_client(request)
    try:
        data = {
            'code': request.POST.get('code'),
            'name': request.POST.get('name'),
            'system': request.POST.get('system', 'goms'),
            'resource': request.POST.get('resource', ''),
            'action': request.POST.get('action', ''),
        }
        print(f"PERM UPDATE: id={perm_id}, data={data}")
        client.put('/permissions/' + str(perm_id), data)
        return redirect('users:roles')
    except ApiException as e:
        print(f"PERM UPDATE ERROR: {e}")
        return JsonResponse({'error': str(e)}, status=400)

def ajax_permission_delete(request, perm_id):
    if request.method != 'POST': return JsonResponse({'error': 'Method not allowed'}, status=405)
    client = _get_client(request)
    try:
        client.delete('/permissions/' + str(perm_id))
        return redirect('users:roles')
    except ApiException as e:
        print(f"PERM DELETE ERROR: {e}")
        return redirect('users:roles')

import json

# ========== ربط الصلاحيات بالأدوار ==========
def ajax_role_permissions(request, role_id):
    client = _get_client(request)
    try:
        result = client.get('/roles/' + str(role_id) + '/permissions')
        perms = result if isinstance(result, list) else result.get('items', [])
        return JsonResponse({'items': perms})
    except Exception as e:
        return JsonResponse({'items': []})
def ajax_link_permission(request, role_id):
    if request.method != 'POST': return JsonResponse({'error': 'Method not allowed'}, status=405)
    client = _get_client(request)
    try:
        data = json.loads(request.body)
        perm_id = data.get('permission_id')
        print(f"LINK: role={role_id}, perm={perm_id}")
        client.post('/roles/' + str(role_id) + '/permissions', {'permission_id': int(perm_id)})
        return JsonResponse({'success': True})
    except ApiException as e:
        print(f"LINK ERROR: {e}")
        return JsonResponse({'error': str(e)}, status=400)
def ajax_link_permission(request, role_id):
    if request.method != 'POST': return JsonResponse({'error': 'Method not allowed'}, status=405)
    client = _get_client(request)
    try:
        data = json.loads(request.body)
        client.post('/roles/' + str(role_id) + '/permissions', {'permission_id': data.get('permission_id')})
        return JsonResponse({'success': True})
    except ApiException as e: return JsonResponse({'error': str(e)}, status=400)

def ajax_unlink_permission(request, role_id):
    if request.method != 'POST': return JsonResponse({'error': 'Method not allowed'}, status=405)
    client = _get_client(request)
    try:
        data = json.loads(request.body)
        client.delete('/roles/' + str(role_id) + '/permissions/' + str(data.get('permission_id')))
        return JsonResponse({'success': True})
    except ApiException as e: return JsonResponse({'error': str(e)}, status=400)
