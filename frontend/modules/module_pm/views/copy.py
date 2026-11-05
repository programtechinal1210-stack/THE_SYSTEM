from datetime import date
from django.http import HttpResponse
from django.shortcuts import render,redirect
from django.views.decorators.http import require_http_methods
from shared.services.api_client import ApiClient,ApiException,UnauthorizedException,ForbiddenException,NotFoundException

@require_http_methods(['GET','POST'])
def copy_plan(request,project_id):
    client=ApiClient(token=request.session.get('access_token'));base=f'/pm/projects/{project_id}'
    try:
        client.get('/pm/planning-references',params={'action':'planning','project_id':str(project_id)})
        request.core_identity=client.get('/auth/me');request.core_modules=client.get('/modules')
        project=client.get(base)
        values={key:request.POST.get(key,'') for key in ('kind','source_id','parent_id','new_code','new_name','rate_date','preview_token')}
        ctx={'project':project,'project_url':base+'/','values':values,'today':date.today().isoformat()}
        if request.method=='POST':
            try:
                if request.POST.get('confirm')=='yes':
                    result=client.post(base+'/copy/apply',data=values)
                    return redirect(base+'/?selected='+result['id'])
                ctx['preview']=client.post(base+'/copy/preview',data=values)
            except (UnauthorizedException,ForbiddenException,NotFoundException):raise
            except ApiException:
                ctx['error']='تعذر النسخ. تحقق من تطابق نوع العنصر والأب، وتفرد الرمز، وأسعار الصرف وتاريخها. أعد المعاينة إذا تغيرت الخطة.'
        choices=[]
        for kind,label in [('phases','مرحلة'),('tasks','مهمة'),('activities','نشاط')]:
            rows=[]
            while True:
                result=client.get(base+'/'+kind,params={'skip':len(rows),'limit':100});rows.extend(result['items'])
                if len(rows)>=result['total']:break
            choices.extend({'id':r['id'],'name':label+' — '+r['name'],'kind':kind} for r in rows)
        ctx['choices']=choices
        return render(request,'pm/copy_plan.html',ctx,status=400 if ctx.get('error') else 200)
    except UnauthorizedException:return redirect('auth:login')
    except ForbiddenException:return HttpResponse('ليس لديك صلاحية نسخ الخطة',status=403)
    except NotFoundException:return HttpResponse('العنصر غير متاح ضمن نطاقك',status=404)
    except ApiException:return HttpResponse('تعذر الاتصال بخدمة التخطيط',status=503)
