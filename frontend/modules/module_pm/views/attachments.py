import requests
from django.http import HttpResponse
from django.shortcuts import render,redirect
from django.views.decorators.http import require_http_methods
from shared.services.api_client import ApiClient,ApiException,UnauthorizedException,ForbiddenException,NotFoundException

@require_http_methods(['GET','POST'])
def attachments(request,project_id,activity_id,attachment_id=None):
    client=ApiClient(token=request.session.get('access_token'))
    base=f'/pm/projects/{project_id}/activities/{activity_id}'
    try:
        request.core_identity=client.get('/auth/me');request.core_modules=client.get('/modules')
        item=client.get(base)
        if attachment_id:
            if request.method!='GET':return HttpResponse(status=405)
            response=requests.get(client.base_url+base+'/attachments/'+str(attachment_id),headers={'Authorization':'Bearer '+client.token},timeout=20)
            if response.status_code!=200:
                client._handle_response(response)
            result=HttpResponse(response.content,content_type=response.headers.get('Content-Type','application/octet-stream'))
            for name in ('Content-Disposition','X-Content-Type-Options','Cache-Control'):
                if name in response.headers:result[name]=response.headers[name]
            return result
        manage=request.core_identity.get('is_admin') or 'pm.planning.manage' in request.core_identity.get('permissions',[])
        if not manage:return HttpResponse('ليس لديك صلاحية رفع المرفقات',status=403)
        error=None
        if request.method=='POST':
            file=request.FILES.get('file')
            if not file or not 0<file.size<=5242880:error='اختر ملفًا بحجم لا يتجاوز 5 MB.'
            else:
                response=requests.post(client.base_url+base+'/attachments',headers={'Authorization':'Bearer '+client.token},files={'file':(file.name,file,file.content_type)},timeout=30)
                if response.status_code==201:return redirect(base+'/')
                if response.status_code in (401,403,404):client._handle_response(response)
                error='تعذر رفع الملف. تحقق من النوع والحجم: PDF أو PNG أو JPEG أو TXT أو CSV.'
        return render(request,'pm/attachment_form.html',{'item':item,'error':error,'back':base+'/'},status=400 if error else 200)
    except UnauthorizedException:return redirect('auth:login')
    except ForbiddenException:return HttpResponse('ليس لديك صلاحية الوصول',status=403)
    except NotFoundException:return HttpResponse('المرفق أو النشاط غير متاح',status=404)
    except (ApiException,requests.RequestException):return HttpResponse('تعذر الاتصال بخدمة المرفقات',status=503)
