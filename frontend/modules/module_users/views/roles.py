from django.shortcuts import render
from shared.services.api_client import ApiClient, ApiException

def roles_management(request):
    client = ApiClient()
    token = request.session.get('access_token')
    if token: client._token = token

    context = {'page_title': 'إدارة الأدوار والصلاحيات', 'active': 'users'}

    try:
        result = client.get('/roles/')
        context['roles'] = result if isinstance(result, list) else result.get('items', [])
    except: context['roles'] = []

    try:
        result = client.get('/permissions/')
        context['permissions'] = result if isinstance(result, list) else result.get('items', [])
    except: context['permissions'] = []

    return render(request, 'users/roles.html', context)
def _get_client(request):
    client = ApiClient()
    token = request.session.get('access_token')
    print(f"TOKEN from cookie: {request.COOKIES.get('access_token', 'NONE')[:20] if request.COOKIES.get('access_token') else 'NONE'}")
    print(f"TOKEN from session: {request.session.get('access_token', 'NONE')[:20] if request.session.get('access_token') else 'NONE'}")
    if token: client._token = token
    print(f"FINAL TOKEN: {client._token[:20] if client._token else 'NONE'}")
    return client