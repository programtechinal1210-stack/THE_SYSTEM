# modules/module_users/views/create.py
from django.shortcuts import render, redirect
from django.contrib import messages
from shared.services.api_client import ApiClient, ApiException

def users_create(request):
    client = ApiClient()
    token = request.session.get('access_token')
    if token:
        client._token = token

    context = {'page_title': 'إنشاء مستخدم', 'active': 'users'}

    if request.method == 'POST':
        data = {
            'username': request.POST.get('username'),
            'password': request.POST.get('password'),
            'full_name': request.POST.get('full_name'),
            'email': request.POST.get('email'),
            'phone': request.POST.get('phone', ''),
            'organization_id': request.POST.get('organization_id') or None,
            'position': request.POST.get('position', ''),
        }
        try:
            data['role_names'] = [request.POST['role']] if request.POST.get('role') else []
            result = client.post('/auth/register', data)
            user_id = result.get('id')
            messages.success(request, 'تم إنشاء المستخدم بنجاح')
            return redirect('users:list')
        except ApiException as e:
            messages.error(request, 'فشل إنشاء المستخدم: ' + str(e))

    return render(request, 'users/create.html', context)
