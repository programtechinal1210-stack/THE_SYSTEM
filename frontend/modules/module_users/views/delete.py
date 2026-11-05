# modules/module_users/views/delete.py
from django.shortcuts import redirect
from django.contrib import messages
from shared.services.api_client import ApiClient, ApiException

def users_delete(request, user_id):
    if request.method != 'POST':
        messages.error(request, 'طريقة غير مسموح بها')
        return redirect('users:list')

    client = ApiClient()
    try:
        client.delete(f'/users/{user_id}')
        messages.success(request, 'تم حذف المستخدم بنجاح')
    except ApiException as e:
        messages.error(request, f'فشل حذف المستخدم: {str(e)}')

    return redirect('users:list')

