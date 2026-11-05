# modules/module_users/views/profile.py
from django.shortcuts import render, redirect
from django.contrib import messages
from shared.services.api_client import ApiClient, ApiException

def users_profile(request):
    client = ApiClient()
    context = {'page_title': 'الملف الشخصي', 'active': 'profile'}

    try:
        user = client.get('/auth/me')
        user_id = user.get('id')
        context['user'] = user
    except ApiException:
        messages.error(request, 'يرجى تسجيل الدخول')
        return redirect('auth:login')

    try:
        cases = client.get('/cases/', params={'created_by': str(user_id), 'limit': 5})
        context['user_cases'] = cases if isinstance(cases, list) else cases.get('items', [])
        context['total_cases'] = len(context['user_cases']) if isinstance(cases, list) else cases.get('total', 0)
    except:
        context['user_cases'] = []
        context['total_cases'] = 0

    try:
        tasks = client.get('/tasks/', params={'assigned_to': str(user_id), 'limit': 5})
        context['user_tasks'] = tasks if isinstance(tasks, list) else tasks.get('items', [])
        context['total_tasks'] = len(context['user_tasks']) if isinstance(tasks, list) else tasks.get('total', 0)
    except:
        context['user_tasks'] = []
        context['total_tasks'] = 0

    if request.method == 'POST':
        data = {
            'full_name': request.POST.get('full_name'),
            'email': request.POST.get('email'),
            'phone': request.POST.get('phone', ''),
        }

        try:
            client.put(f'/users/{user_id}', data)

            current_password = request.POST.get('current_password')
            new_password = request.POST.get('new_password')
            if current_password and new_password:
                try:
                    client.put(f'/users/{user_id}/password', {
                        'current_password': current_password,
                        'new_password': new_password
                    })
                except ApiException as e:
                    messages.error(request, f'فشل تغيير كلمة المرور: {str(e)}')
                    return render(request, 'users/profile.html', context)

            messages.success(request, 'تم تحديث الملف الشخصي بنجاح')
            return redirect('users:profile')
        except ApiException as e:
            messages.error(request, f'فشل تحديث الملف الشخصي: {str(e)}')

    return render(request, 'users/profile.html', context)

