# modules/module_users/views/edit.py
from django.shortcuts import render, redirect
from django.contrib import messages
from shared.services.api_client import ApiClient, ApiException

def users_edit(request, user_id):
    client = ApiClient()
    context = {'page_title': 'تعديل مستخدم', 'active': 'users'}

    try:
        user = client.get(f'/users/{user_id}')
        context['user'] = user
    except ApiException:
        messages.error(request, 'المستخدم غير موجود')
        return redirect('users:list')

    try:
        roles = client.get('/roles/')
        context['roles'] = roles if isinstance(roles, list) else roles.get('items', [])
    except:
        context['roles'] = []

    if request.method == 'POST':
        data = {
            'full_name': request.POST.get('full_name'),
            'email': request.POST.get('email'),
            'phone': request.POST.get('phone', ''),
            'position': request.POST.get('position', ''),
            'is_active': request.POST.get('is_active', 'true') == 'true',
        }

        try:
            client.put(f'/users/{user_id}', data)

            role = request.POST.get('role')
            if role:
                client.post('/users/' + str(user_id) + '/roles', {'role_name': role})

            password = request.POST.get('password')
            if password:
                client.put('/users/' + str(user_id) + '/password', {'new_password': password})

            messages.success(request, 'تم تحديث المستخدم بنجاح')
            return redirect('users:list')
        except ApiException as e:
            messages.error(request, 'فشل تحديث المستخدم: ' + str(e))

    return render(request, 'users/edit.html', context)
