from uuid import UUID
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods
from shared.services.api_client import ApiClient, ApiException, UnauthorizedException, ForbiddenException, NotFoundException
from ..services.planning import KINDS, allowed


@require_http_methods(['GET', 'POST'])
def recycle(request):
    client = ApiClient(token=request.session.get('access_token'))
    kind = request.GET.get('kind', 'projects')
    if kind not in KINDS:
        return HttpResponse(status=404)
    try:
        skip = max(0, int(request.GET.get('skip', 0)))
    except ValueError:
        return HttpResponse(status=400)
    try:
        client.get('/pm/')
        request.core_identity = identity = client.get('/auth/me')
        request.core_modules = client.get('/modules')
        rows = client.get('/recycle', params={'entity_type':'pm.'+kind, 'skip':skip, 'limit':50})['items']
        error = None
        if request.method == 'POST':
            try:
                bin_id = UUID(request.POST.get('bin_id', '')).hex
            except ValueError:
                return HttpResponse(status=400)
            if bin_id not in {r['id'] for r in rows}:
                return HttpResponse('العنصر غير متاح ضمن نطاقك', status=404)
            try:
                client.post('/recycle/'+bin_id+'/restore')
                return redirect(request.get_full_path())
            except (UnauthorizedException, ForbiddenException, NotFoundException):
                raise
            except ApiException:
                error = 'تعذرت الاستعادة. استعد المشروع والعنصر الأب أولًا ثم حاول مجددًا.'
        can_restore = allowed(identity,'core.recycle.manage') and allowed(identity,'pm.projects.update' if kind=='projects' else 'pm.planning.manage')
        return render(request,'pm/recycle.html',{'page_title':'محذوفات إدارة المشاريع','items':rows,
            'kinds':[(key,value[0]) for key,value in KINDS.items()], 'kind':kind,'error':error,'can_restore':can_restore,
            'previous':skip-50 if skip else None,'following':skip+50 if len(rows)==50 else None})
    except UnauthorizedException:
        return redirect('auth:login')
    except ForbiddenException:
        return HttpResponse('ليس لديك صلاحية سلة المحذوفات',status=403)
    except NotFoundException:
        return HttpResponse('العنصر غير متاح ضمن نطاقك',status=404)
    except ApiException:
        return HttpResponse('تعذر تحميل سلة المحذوفات',status=503)
