from django.http import JsonResponse
from shared.services.api_client import ApiClient, ApiException

def ajax_permissions_list(request):
    client = ApiClient()
    token = request.session.get('access_token')
    if token: client._token = token
    try:
        result = client.get('/permissions/')
        perms = result if isinstance(result, list) else result.get('items', [])
        return JsonResponse({'items': perms, 'total': len(perms)})
    except ApiException as e:
        return JsonResponse({'items': [], 'total': 0, 'error': str(e)})
