import requests
from uuid import UUID

from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from shared.services.api_client import (
    ApiClient, ApiException, ConflictException, ForbiddenException, NotFoundException,
    UnauthorizedException, ValidationException,
)
from ..services.planning import allowed


TABS = {'completed', 'review', 'acceptance', 'history'}
STATUS_LABELS = {
    'in_review': 'قيد المراجعة',
    'ready_for_acceptance': 'جاهز للاستلام',
    'accepted': 'تم الاستلام',
    'requires_treatment': 'يتطلب معالجة',
    'closed': 'مغلق رسمياً',
    'open': 'مفتوحة',
    'in_progress': 'قيد المعالجة',
    'resolved': 'بانتظار التحقق',
    'verified': 'متحقق منها',
}
EVENT_LABELS = {
    'review_started': 'بدء مراجعة الاكتمال',
    'review_restarted': 'إعادة المراجعة بعد المعالجة',
    'review_result': 'قرار مراجعة',
    'acceptance_decision': 'قرار الاستلام',
    'project_close': 'إغلاق المشروع رسمياً',
    'project_closed': 'إغلاق المشروع رسمياً',
    'blocking_issue_added': 'إضافة ملاحظة مانعة',
    'issue_in_progress': 'بدء معالجة ملاحظة',
    'issue_resolved': 'تسجيل معالجة الملاحظة',
    'issue_verified': 'التحقق من معالجة الملاحظة',
}


def _workspace_context(client, project_id, identity, active_tab):
    data = client.get(f'/pm/projects/{project_id}/completion')
    references = client.get(
        f'/pm/projects/{project_id}/ui-references', params={'section': 'completion'})
    permissions = set(identity.get('permissions', []))
    can = lambda permission: identity.get('is_admin', False) or permission in permissions
    project = data['project']
    for phase in project['phases']:
        phase['execution_label'] = 'مكتملة تنفيذياً' if phase['execution_complete'] else 'قيد التنفيذ'
        phase['completion_label'] = 'مغلقة رسمياً' if phase['completion_complete'] else 'غير مغلقة'
        for task in phase['tasks']:
            task['execution_label'] = 'مكتملة تنفيذياً' if task['execution_complete'] else 'قيد التنفيذ'
            task['completion_label'] = 'مغلقة رسمياً' if task['completion_complete'] else 'غير مغلقة'
            for activity in task['activities']:
                case = activity['case']
                activity['completion_status'] = case['status'] if case else 'executively_complete'
                activity['completion_label'] = STATUS_LABELS.get(
                    activity['completion_status'], 'مكتمل تنفيذياً')
                activity['can_start_review'] = (
                    can('pm.completion.review')
                    and activity['execution_complete']
                    and (not case or case['status'] == 'requires_treatment')
                    and not any(issue['blocking'] and issue['status'] != 'verified'
                                for issue in activity['issues'])
                )
                activity['can_submit_review'] = bool(
                    can('pm.completion.review') and case and case['status'] == 'in_review')
                activity['can_accept'] = bool(
                    can('pm.completion.accept') and case and case['status'] == 'ready_for_acceptance')
                activity['issues'] = [
                    {**issue, 'status_label': STATUS_LABELS.get(issue['status'], issue['status']),
                     'can_manage': can('pm.completion.issues.manage'),
                     'can_verify': can('pm.completion.issues.verify')}
                    for issue in activity['issues']
                ]
                for event in activity['events']:
                    event['action_label'] = EVENT_LABELS.get(event['action'], event['action'])
                    event['receipt_url'] = (
                        reverse('pm:completion-receipt', kwargs={
                            'project_id': project_id, 'case_id': UUID(case['id'])})
                        if can('pm.completion.documents.view')
                        and event['action'] == 'acceptance_decision'
                        and event['to_status'] in ('accepted', 'closed')
                        else ''
                    )
                for document in activity['documents']:
                    document['download_url'] = reverse(
                        'pm:completion-document-download',
                        kwargs={'project_id': project_id, 'case_id': UUID(document['case_id']),
                                'attachment_id': UUID(document['id'])})
    data['project'] = project
    data['project_closed'] = bool(data['project_closed'])
    data['can_close'] = can('pm.completion.close') and not data['project_closed']
    data['can_create_issue'] = can('pm.completion.issues.manage')
    data['can_upload_document'] = can('pm.completion.documents.manage')
    data['can_view_documents'] = can('pm.completion.documents.view')
    data['can_review'] = can('pm.completion.review')
    data['can_accept'] = can('pm.completion.accept')
    data['close_blocked'] = not data['project_execution_complete'] or not data['documents_complete'] or (
        data['counts']['accepted'] != data['counts']['eligible']
    ) or bool(data['counts'].get('blocking_issues', 0))
    data['project_close_events'] = [
        {**event, 'action_label': EVENT_LABELS.get(event['action'], event['action'])}
        for event in data['project_events']
    ]
    all_events = []
    for phase in project['phases']:
        for task in phase['tasks']:
            for activity in task['activities']:
                for event in activity['events']:
                    all_events.append({
                        **event, 'phase_name': phase['name'], 'task_name': task['name'],
                        'activity_name': activity['name'],
                    })
    all_events.extend({
        **event, 'activity_name': project['name'],
    } for event in data['project_close_events'])
    data.update({
        'references': references,
        'active_tab': active_tab,
        'page_title': 'اكتمال المشروع — ' + project['name'],
        'status_labels': STATUS_LABELS,
        'all_events': sorted(all_events, key=lambda event: event['created_at'], reverse=True),
    })
    return data


def _identity(request, client):
    client.get('/pm/')
    identity = client.get('/auth/me')
    request.core_identity = identity
    request.core_modules = client.get('/modules')
    return identity


@require_http_methods(['GET'])
def completion_center(request):
    client = ApiClient(token=request.session.get('access_token'))
    try:
        identity = _identity(request, client)
        if not allowed(identity, 'pm.completion.view'):
            return HttpResponse('ليس لديك صلاحية عرض مركز الاكتمال', status=403)
        center = client.get('/pm/completion-center')
        for project in center['items']:
            project['href'] = reverse(
                'pm:completion-workspace', kwargs={'project_id': UUID(project['id'])})
            project['report_href'] = reverse(
                'pm:completion-report', kwargs={'project_id': UUID(project['id'])})
            project['close_status'] = 'مغلق رسمياً' if project['project_closed'] else 'مفتوح'
            project['status_label'] = {
                'issued': 'صادر التوجيه', 'planning': 'قيد التخطيط', 'planned': 'تم التخطيط',
                'in_progress': 'قيد التنفيذ', 'completed': 'مكتمل',
            }.get(project['status'], project['status'])
            project['completion_percent'] = (
                round(project['executively_complete'] * 100 / project['activity_count'])
                if project['activity_count'] else 0
            )
        return render(request, 'pm/completion_center.html', {
            'page_title': 'مركز الاكتمال والاستلام',
            'projects': center['items'],
            'total_projects': len(center['items']),
            'total_ready': sum(item['executively_complete'] > 0 for item in center['items']),
            'total_open_issues': sum(item['open_issues'] for item in center['items']),
            'total_closed': sum(item['project_closed'] for item in center['items']),
        })
    except UnauthorizedException:
        return redirect('auth:login')
    except ForbiddenException:
        return HttpResponse('ليس لديك صلاحية عرض مركز الاكتمال', status=403)
    except ApiException:
        return HttpResponse('تعذر تحميل مركز الاكتمال؛ حاول مجددًا', status=503)


@require_http_methods(['GET', 'POST'])
def completion_workspace(request, project_id):
    client = ApiClient(token=request.session.get('access_token'))
    error = ''
    saved = request.GET.get('saved') == '1'
    active_tab = request.GET.get('tab', 'completed')
    if request.method == 'POST':
        active_tab = request.POST.get('tab', 'completed')
    if active_tab not in TABS:
        return HttpResponse('قسم الاكتمال غير صالح', status=400)
    try:
        identity = _identity(request, client)
        if not allowed(identity, 'pm.completion.view'):
            return HttpResponse('ليس لديك صلاحية عرض اكتمال المشروع', status=403)
        base = f'/pm/projects/{project_id}/completion'
        if request.method == 'POST':
            action = request.POST.get('action', '')
            activity_id = request.POST.get('activity_id', '')
            issue_id = request.POST.get('issue_id', '')
            case_id = request.POST.get('case_id', '')
            if action == 'start_review':
                client.post(f'{base}/activities/{activity_id}/review/start')
                active_tab = 'review'
            elif action == 'review':
                client.post(f'{base}/activities/{activity_id}/review', {
                    'result': request.POST.get('result', ''),
                    'notes': request.POST.get('notes', ''),
                    'missing_requirement': request.POST.get('missing_requirement', ''),
                    'corrective_action': request.POST.get('corrective_action', ''),
                    'owner_user_id': request.POST.get('owner_user_id') or None,
                    'target_date': request.POST.get('target_date') or None,
                })
                active_tab = 'review'
            elif action == 'acceptance':
                client.post(f'{base}/activities/{activity_id}/acceptance', {
                    'result': request.POST.get('result', ''),
                    'acceptance_type': request.POST.get('acceptance_type', ''),
                    'reference': request.POST.get('reference', ''),
                    'notes': request.POST.get('notes', ''),
                })
                active_tab = 'acceptance'
            elif action == 'close':
                client.post(f'{base}/close', {'reason': request.POST.get('reason', '')})
                active_tab = 'acceptance'
            elif action == 'create_issue':
                client.post(f'{base}/cases/{case_id}/issues', {
                    'description': request.POST.get('description', ''),
                    'issue_type': request.POST.get('issue_type', ''),
                    'severity': request.POST.get('severity', 'medium'),
                    'blocking': request.POST.get('blocking') == 'on',
                    'owner_user_id': request.POST.get('owner_user_id') or None,
                    'target_date': request.POST.get('target_date') or None,
                })
                active_tab = 'review'
            elif action == 'issue_transition':
                target = request.POST.get('target', '')
                if target not in {'in_progress', 'resolved', 'verified'}:
                    return HttpResponse('انتقال الملاحظة غير صالح', status=400)
                client.post(f'{base}/issues/{issue_id}/{target}', {
                    'notes': request.POST.get('notes', '')})
                active_tab = 'history'
            elif action == 'upload_document':
                file = request.FILES.get('file')
                if not file:
                    error = 'اختر ملفاً لإرفاقه.'
                else:
                    params = {'category': request.POST.get('category', '')}
                    if request.POST.get('issue_id'):
                        params['issue_id'] = request.POST['issue_id']
                    response = requests.post(
                        client._build_url(f'{base}/cases/{case_id}/documents'),
                        headers={'Authorization': 'Bearer ' + (client.token or '')},
                        params=params,
                        files={'file': (file.name, file, file.content_type)},
                        timeout=30,
                    )
                    if response.status_code != 201:
                        client._handle_response(response)
                    active_tab = 'history'
            else:
                return HttpResponse('إجراء الاكتمال غير معروف', status=400)
            if not error:
                return redirect(
                    reverse('pm:completion-workspace', kwargs={'project_id': project_id})
                    + f'?tab={active_tab}&saved=1')
    except UnauthorizedException:
        return redirect('auth:login')
    except ForbiddenException:
        return HttpResponse('ليس لديك صلاحية لتنفيذ هذا الإجراء', status=403)
    except NotFoundException:
        return HttpResponse('المشروع أو عنصر الاكتمال غير متاح ضمن نطاقك', status=404)
    except ConflictException as exc:
        error = str(exc)
    except ValidationException as exc:
        error = str(exc)
    except requests.RequestException:
        error = 'تعذر رفع المستند؛ تحقق من اتصال الخدمة ثم أعد المحاولة.'
    except ApiException:
        return HttpResponse('تعذر الاتصال بخدمة الاكتمال؛ حاول مجددًا', status=503)
    try:
        context = _workspace_context(client, project_id, identity, active_tab)
    except UnauthorizedException:
        return redirect('auth:login')
    except ForbiddenException:
        return HttpResponse('ليس لديك صلاحية عرض اكتمال المشروع', status=403)
    except NotFoundException:
        return HttpResponse('المشروع غير متاح ضمن نطاقك', status=404)
    except ApiException:
        return HttpResponse('تعذر تحديث بيانات الاكتمال؛ حاول مجددًا', status=503)
    context.update({'error': error, 'saved': saved, 'project_id': project_id})
    return render(request, 'pm/completion_workspace.html', context, status=409 if error else 200)


@require_http_methods(['GET'])
def completion_report(request, project_id):
    """Read-only completion, acceptance, and closure report for one scoped project."""
    client = ApiClient(token=request.session.get('access_token'))
    try:
        identity = _identity(request, client)
        if not allowed(identity, 'pm.completion.view'):
            return HttpResponse('ليس لديك صلاحية عرض تقرير الاكتمال', status=403)
        context = _workspace_context(client, project_id, identity, 'history')
        context['page_title'] = 'تقرير الاكتمال والاستلام والإغلاق — ' + context['project']['name']
        activities = [activity for phase in context['project']['phases']
                      for task in phase['tasks'] for activity in task['activities']]
        context['activity_count'] = len(activities)
        context['ready_count'] = sum(
            activity['completion_status'] == 'ready_for_acceptance' for activity in activities)
        return render(request, 'pm/completion_report.html', context)
    except UnauthorizedException:
        return redirect('auth:login')
    except ForbiddenException:
        return HttpResponse('ليس لديك صلاحية عرض تقرير الاكتمال', status=403)
    except ApiException:
        return HttpResponse('تعذر تحميل تقرير الاكتمال؛ حاول مجددًا', status=503)


@require_http_methods(['GET'])
def completion_receipt(request, project_id, case_id):
    client = ApiClient(token=request.session.get('access_token'))
    try:
        identity = _identity(request, client)
        if not allowed(identity, 'pm.completion.documents.view'):
            return HttpResponse('ليس لديك صلاحية عرض محاضر الاستلام', status=403)
        data = client.get(f'/pm/projects/{project_id}/completion')
        selected = None
        for phase in data['project']['phases']:
            for task in phase['tasks']:
                for activity in task['activities']:
                    case = activity['case']
                    if case and UUID(case['id']) == case_id:
                        event = next((item for item in activity['events']
                                      if item['action'] == 'acceptance_decision'
                                      and item['to_status'] in ('accepted', 'closed')), None)
                        if event:
                            selected = {'activity': activity, 'event': event}
        if not selected:
            return HttpResponse('محضر الاستلام غير متاح', status=404)
        return render(request, 'pm/completion_receipt.html', {
            'project': data['project'], **selected,
        })
    except UnauthorizedException:
        return redirect('auth:login')
    except ForbiddenException:
        return HttpResponse('ليس لديك صلاحية عرض محاضر الاستلام', status=403)
    except NotFoundException:
        return HttpResponse('المشروع غير متاح ضمن نطاقك', status=404)
    except ApiException:
        return HttpResponse('تعذر تحميل محضر الاستلام؛ حاول مجددًا', status=503)


@require_http_methods(['GET'])
def completion_document_download(request, project_id, case_id, attachment_id):
    client = ApiClient(token=request.session.get('access_token'))
    try:
        identity = _identity(request, client)
        if not allowed(identity, 'pm.completion.documents.view'):
            return HttpResponse('ليس لديك صلاحية عرض مستندات الاكتمال', status=403)
        content, content_type, disposition = client.download(
            f'/pm/projects/{project_id}/completion/cases/{case_id}/documents/{attachment_id}')
        response = HttpResponse(content, content_type=content_type)
        if disposition:
            response['Content-Disposition'] = disposition
        response['X-Content-Type-Options'] = 'nosniff'
        response['Cache-Control'] = 'no-store'
        return response
    except UnauthorizedException:
        return redirect('auth:login')
    except ForbiddenException:
        return HttpResponse('ليس لديك صلاحية عرض مستندات الاكتمال', status=403)
    except NotFoundException:
        return HttpResponse('المستند غير متاح ضمن نطاقك', status=404)
    except ApiException:
        return HttpResponse('تعذر تنزيل المستند؛ حاول مجددًا', status=503)
