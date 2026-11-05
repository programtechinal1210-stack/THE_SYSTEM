from uuid import UUID
from django.shortcuts import render,redirect
from django.http import HttpResponse
from django.views.decorators.http import require_http_methods
from shared.services.api_client import ApiClient,ApiException,UnauthorizedException,ForbiddenException,NotFoundException
from ..services.planning import allowed

LABELS={'issued':'صادر التوجيه','planning':'قيد التخطيط','planned':'تم التخطيط','in_progress':'قيد التنفيذ',
        'pending':'قيد المراجعة','approved':'تم الإقرار','rejected':'مرفوض'}


def build_approval_context(client, identity, project_id):
    """Load the canonical approval data for either the page or planning tab."""
    base = f'/pm/projects/{project_id}'
    data = client.get(base + '/approval')
    try:
        phases = {str(row['id']).replace('-', '').lower(): row
                  for row in client.get(base + '/phases').get('items', [])}
        tasks = {str(row['id']).replace('-', '').lower(): row
                 for row in client.get(base + '/tasks').get('items', [])}
        requirements = {}
        for requirement in client.get(base + '/requirements').get('items', []):
            requirements.setdefault(str(requirement.get('activity_id', '')).replace('-', '').lower(), []).append(requirement)
        for activity in data.get('activities', []):
            task = tasks.get(str(activity.get('task_id', '')).replace('-', '').lower())
            phase = phases.get(str(task.get('phase_id', '')).replace('-', '').lower()) if task else None
            activity.update({
                'task_name': task.get('name') if task else activity.get('task_name'),
                'task_code': task.get('task_code') if task else activity.get('task_code'),
                'phase_name': phase.get('name') if phase else activity.get('phase_name'),
                'phase_code': phase.get('phase_code') if phase else activity.get('phase_code'),
                'hierarchy_valid': bool(task and phase),
                'requirements': requirements.get(str(activity.get('id', '')).replace('-', '').lower(), []),
            })
    except ApiException:
        pass
    context = dict(data)
    context['error'] = ''
    context['result'] = None
    context['status_label'] = LABELS.get(data['project']['status'], data['project']['status'])
    total = data.get('stats', {}).get('total', 0)
    context['approval_percent'] = round((data.get('stats', {}).get('approved', 0) / total) * 100) if total else 0
    context['manage'] = allowed(identity, 'pm.planning.manage') and data['project']['status'] in ('planning', 'planned')
    context['project_status'] = data['project']['status']
    context['approval_block_reason'] = (
        'الإقرار متاح فقط عندما تكون الخطة في حالة قيد التخطيط أو تم التخطيط.'
        if data['project']['status'] not in ('planning', 'planned') else '')
    context['transitions'] = [
        {'code': value, 'label': LABELS[value]}
        for value in {'issued': ['planning'], 'planning': ['planned'], 'planned': ['planning', 'in_progress']}.get(data['project']['status'], [])
    ] if allowed(identity, 'pm.projects.update') else []
    for row in context['activities']:
        row['status_label'] = LABELS[row['approval_status']]
        row['edit_url'] = f"{base}/activities/{row['id']}/edit/"
    return context


@require_http_methods(['GET','POST'])
def approval(request,project_id):
    client=ApiClient(token=request.session.get('access_token'))
    base=f'/pm/projects/{project_id}'
    try:
        client.get('/pm/')
        request.core_identity=client.get('/auth/me');request.core_modules=client.get('/modules')
        ctx={'page_title':'إقرار خطة المشروع','project_url':base+'/','error':''}
        if request.method=='POST':
            command=request.POST.get('command')
            try:
                if command=='transition':
                    target_status = request.POST.get('status')
                    client.post(base+'/planning-status',data={'status':target_status})
                    if target_status == 'planning':
                        return redirect(base + '/')
                    if target_status == 'planned':
                        return redirect('/pm/execution/' if allowed(request.core_identity, 'pm.execution.view') else '/pm/')
                elif command=='approve-all':
                    result=client.post(base+'/approve-all',data={})
                    ctx['result']=result
                elif command=='decision':
                    aid=UUID(request.POST.get('activity_id',''))
                    client.post(base+'/approval/'+str(aid),data={'decision':request.POST.get('decision'),'reason':request.POST.get('reason','')})
                else:return HttpResponse(status=400)
            except ValueError:return HttpResponse(status=400)
            except ApiException as exc:
                if isinstance(exc,(UnauthorizedException,ForbiddenException,NotFoundException)):raise
                ctx['error']=str(exc)
        if request.GET.get('embedded') == '1' and not ctx['error'] and request.method == 'POST':
            return redirect(base + '/?step=5')
        approval_context = build_approval_context(client, request.core_identity, project_id)
        ctx.update(approval_context)
        ctx['approval_content'] = approval_context
        ctx['approval_post_url'] = request.path
        ctx['approval_embedded'] = False
        return render(request,'pm/approval.html',ctx,status=400 if ctx['error'] else 200)
    except UnauthorizedException:return redirect('auth:login')
    except ForbiddenException:return HttpResponse('ليس لديك صلاحية',status=403)
    except NotFoundException:return HttpResponse('المشروع غير متاح ضمن نطاقك',status=404)
    except ApiException:return HttpResponse('تعذر تحميل إقرار التخطيط',status=503)
