from django.urls import path
from django.http import HttpResponseNotFound
from core import workspace
from shared.services.api_client import ApiClient, ApiException
from django.http import JsonResponse

app_name = 'audit'

def summary(request):
    try:
        return JsonResponse(ApiClient().get('/audit/logs/summary', request.GET.dict()))
    except ApiException:
        return JsonResponse({'detail': 'Audit service unavailable or access denied'}, status=403)

def deferred(request):
    return HttpResponseNotFound('This optional module is not enabled in Core 1.0')

urlpatterns = [
    path('', workspace.page, {'section': 'audit'}, name='index'),
    path('logs/', workspace.page, {'section': 'audit'}, name='logs'),
    path('dashboard/', workspace.page, {'section': 'audit'}, name='dashboard'),
    path('api/stats/', summary, name='api_stats'),
    path('exports/', workspace.audit_export, name='exports'),
] + [path(name + '/', deferred, name=name) for name in ('followups','execution','anomalies','alerts')]
