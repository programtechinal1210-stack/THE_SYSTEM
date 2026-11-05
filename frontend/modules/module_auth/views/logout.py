from django.shortcuts import redirect
from django.contrib import messages
from shared.services.api_client import ApiClient
import sys

from django.views.decorators.http import require_POST

@require_POST
def logout_view(request):
    """تسجيل الخروج مع تدقيق"""

    token = request.session.get('access_token', '')
    if token:
        try:
            client = ApiClient(token=token)
            client.post("/auth/logout", include_auth=True)
        except:
            pass

    # حفظ رسالة للمستخدم
    messages.success(request, 'تم تسجيل الخروج بنجاح 👋')
    
    request.session.flush()
    
    response = redirect('/auth/login/')
    response.delete_cookie('sessionid')
    response.delete_cookie('csrftoken')
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response
