from django.http import HttpResponse
from django.shortcuts import render,redirect
from django.views.decorators.http import require_http_methods
from shared.services.api_client import ApiClient,ApiException,UnauthorizedException,ForbiddenException,NotFoundException

@require_http_methods(['GET','POST'])
def hierarchy(request,project_id):
    client=ApiClient(token=request.session.get('access_token'));base=f'/pm/projects/{project_id}'
    try:
        client.get('/pm/')
        request.core_identity=client.get('/auth/me');request.core_modules=client.get('/modules')
        # This page performs mutations; references endpoint enforces manage + project scope.
        client.get('/pm/planning-references',params={'action':'planning','project_id':str(project_id)})
        project=client.get(base)
        ctx={'page_title':'تنظيم التخطيط الهرمي','project':project,'project_url':base+'/','values':{},'error':''}
        if request.method=='POST':
            data={k:request.POST.get(k,'') for k in ('kind','entity_id','operation','new_code','new_name','preview_token')}
            data['target_id']=request.POST.get('target_id') or None
            ctx['values']=data
            try:
                if request.POST.get('confirm')=='yes':
                    client.post(base+'/hierarchy/apply',data=data)
                    return redirect(base+'/')
                ctx['preview']=client.post(base+'/hierarchy/preview',data=data)
            except ApiException as exc:
                if isinstance(exc,(UnauthorizedException,ForbiddenException,NotFoundException)):raise
                ctx['error']=str(exc)
        choices=[]
        for kind,label in [('phases','مرحلة'),('tasks','مهمة'),('activities','نشاط')]:
            rows=[]
            while True:
                part=client.get(base+'/'+kind,params={'skip':len(rows),'limit':100});rows.extend(part['items'])
                if len(rows)>=part['total'] or not part['items']:break
            choices.extend({'id':r['id'],'name':label+' — '+r['name'],'kind':kind} for r in rows)
        ctx['choices']=choices
        return render(request,'pm/hierarchy.html',ctx,status=400 if ctx['error'] else 200)
    except UnauthorizedException:return redirect('auth:login')
    except ForbiddenException:return HttpResponse('ليس لديك صلاحية تنظيم الخطة',status=403)
    except NotFoundException:return HttpResponse('المشروع غير متاح',status=404)
    except ApiException:return HttpResponse('تعذر تحميل الخطة',status=503)
