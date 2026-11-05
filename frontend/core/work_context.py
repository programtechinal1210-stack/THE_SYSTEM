from django.http import HttpResponse, HttpResponseRedirect
from django.views.decorators.http import require_POST
from django.utils.http import url_has_allowed_host_and_scheme
from shared.services.api_client import ApiClient, ApiException


@require_POST
def choose(request):
    try:
        ApiClient(token=request.session.get('access_token')).put('/profile/work-context',
            {'organization_id': request.POST.get('organization_id', '')})
    except ApiException:
        return HttpResponse('تعذر اختيار الجهة؛ تحقق من صلاحية الوصول إليها', status=403)
    target = request.POST.get('next', '/')
    if not url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        target = '/'
    from urllib.parse import urlsplit
    return HttpResponseRedirect(urlsplit(target).path or '/')
