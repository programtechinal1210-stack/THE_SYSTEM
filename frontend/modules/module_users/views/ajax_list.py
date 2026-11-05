from django.shortcuts import render
from django.http import JsonResponse
from shared.services.api_client import ApiClient, ApiException

def ajax_users_list(request):
    client = ApiClient()
    token = request.session.get('access_token')
    if token:
        client._token = token

    params = {'page': request.GET.get('page', 1), 'limit': request.GET.get('limit', 20),
              'search': request.GET.get('search'), 'role': request.GET.get('role'),
              'is_active': request.GET.get('is_active')}
    params = {k: v for k, v in params.items() if v}

    try:
        params['skip'] = max(0, int(params.pop('page', 1)) - 1) * int(params['limit'])
        result = client.get('/users/', params=params)
        users = result if isinstance(result, list) else result.get('items', [])
        total = client.get('/users/summary', params=params)['total']
        return JsonResponse({'items': users, 'total': total})
    except (ApiException, ValueError) as e:
        return JsonResponse({'items': [], 'total': 0, 'error': str(e)})
def ajax_roles_list(request):
    client = ApiClient()
    token = request.session.get('access_token')
    if token: client._token = token
    try:
        result = client.get('/roles/')
        roles = result if isinstance(result, list) else result.get('items', [])
        return JsonResponse({'items': roles, 'total': len(roles)})
    except (ApiException, ValueError) as e:
        return JsonResponse({'items': [], 'total': 0})
def ajax_organizations_list(request):
    client = ApiClient()
    token = request.session.get('access_token')
    if token: client._token = token
    try:
        result = client.get('/org-units')
        orgs = result if isinstance(result, list) else result.get('items', [])
        return JsonResponse({'items': orgs})
    except: return JsonResponse({'items': []})