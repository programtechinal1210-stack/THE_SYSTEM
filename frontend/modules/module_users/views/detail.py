from django.shortcuts import render
from shared.services.api_client import ApiClient, ApiException, NotFoundException, ForbiddenException


def users_detail(request, user_id):
    context = {'section': 'user_detail', 'page_title': 'تفاصيل المستخدم',
               'headings': ['البيان', 'القيمة'], 'forms': []}
    try:
        user = ApiClient().get('/users/' + str(user_id))
        context['rows'] = [
            ['الاسم', user['full_name']], ['اسم المستخدم', user['username']],
            ['البريد', user['email']], ['الوحدة التنظيمية', user['organization_id']],
            ['الأدوار', '، '.join(user.get('roles', []))],
            ['الحالة', 'نشط' if user['is_active'] else 'معطل'],
        ]
        return render(request, 'core/workspace.html', context)
    except ApiException as exc:
        context['error'] = str(exc)
        status = 404 if isinstance(exc, NotFoundException) else 403 if isinstance(exc, ForbiddenException) else 502
        return render(request, 'core/workspace.html', context, status=status)
