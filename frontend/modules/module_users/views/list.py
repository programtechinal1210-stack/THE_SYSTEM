from django.shortcuts import render
from shared.services.api_client import ApiClient, ApiException

def users_list(request):
    client = ApiClient()
    token = request.session.get('access_token')
    if token:
        client._token = token

    context = {'page_title': 'المستخدمون', 'active': 'users', 'users': [], 'total': 0, 'roles': []}

    params = {'page': request.GET.get('page', 1), 'limit': request.GET.get('limit', 20),
              'search': request.GET.get('search'), 'role': request.GET.get('role'),
              'is_active': request.GET.get('is_active')}
    params = {k: v for k, v in params.items() if v}

    try:
        result = client.get('/users/', params=params)
        if isinstance(result, list):
            context['users'] = result
            context['total'] = len(result)
        else:
            context['users'] = result.get('items', [])
            context['total'] = result.get('total', 0)
    except ApiException as e:
        context['error'] = str(e)

    try:
        roles_result = client.get('/roles/')
        context['roles'] = roles_result if isinstance(roles_result, list) else roles_result.get('items', [])
    except:
        pass

    return render(request, 'users/list.html', context)
