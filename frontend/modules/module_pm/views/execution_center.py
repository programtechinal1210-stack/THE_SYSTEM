from datetime import date
from decimal import Decimal
from uuid import UUID

from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from shared.services.api_client import (
    ApiClient, ApiException, ConflictException, ForbiddenException, NotFoundException,
    UnauthorizedException,
)
from ..services.planning import allowed


PROJECT_STATES = {
    'planned': 'جاهز لبدء التنفيذ',
    'in_progress': 'قيد التنفيذ',
}
EXECUTION_CENTER_STATES = {'planned', 'in_progress'}
EXECUTION_BUCKET_LABELS = {
    'all': 'الكل',
    'in_progress': 'قيد التنفيذ',
    'follow_up': 'تحتاج متابعة',
    'ready_for_completion': 'جاهزة للاكتمال',
}


def execution_progress(activities, orders):
    # Activity quantities have different units. Match the execution workspace's
    # per-activity average instead of adding unlike quantities together.
    values = []
    for activity in activities:
        planned = Decimal(str(activity.get('planned_quantity') or 0))
        if planned <= 0:
            continue
        actual = sum((Decimal(str(order.get('actual_quantity_snapshot') or 0))
                      for order in orders if order.get('status') != 'rejected'
                      and str(order.get('activity_id')) == str(activity.get('id'))), Decimal('0'))
        values.append(min(actual * 100 / planned, Decimal('100')))
    if not values:
        return {'value': None, 'label': 'لا تتوفر بيانات كافية', 'available': False}
    return {'value': round(sum(values) / len(values)), 'label': 'الإنجاز الفعلي', 'available': True}


def execution_order_stats(activities, orders):
    """Return display-only counts from the existing work-order read model."""
    activity_progress = {}
    for activity in activities:
        planned = Decimal(str(activity.get('planned_quantity') or 0))
        actual = sum((Decimal(str(order.get('actual_quantity_snapshot') or 0))
                      for order in orders
                      if order.get('status') != 'rejected'
                      and str(order.get('activity_id')) == str(activity.get('id'))), Decimal('0'))
        activity_progress[str(activity.get('id'))] = (
            min(actual * 100 / planned, Decimal('100')) if planned > 0 else None
        )
    completed = sum(order.get('status') in ('completed', 'closed') for order in orders)
    open_orders = sum(order.get('status') in ('issued', 'in_progress') for order in orders)
    today = date.today().isoformat()
    follow_up = sum(
        bool(activity.get('planned_end_date') and str(activity['planned_end_date'])[:10] < today
             and activity_progress.get(str(activity.get('id'))) != 100)
        for activity in activities
    )
    return {'total': len(orders), 'completed': completed, 'open': open_orders,
            'follow_up': follow_up}


@require_http_methods(['GET', 'POST'])
def execution_center(request):
    client = ApiClient(token=request.session.get('access_token'))
    try:
        client.get('/pm/')
        identity = client.get('/auth/me')
        request.core_identity = identity
        request.core_modules = client.get('/modules')
        if not allowed(identity, 'pm.execution.view'):
            return HttpResponse('ليس لديك صلاحية العرض', status=403)

        can_start = allowed(identity, 'pm.projects.update')
        if request.method == 'POST':
            if request.POST.get('command') != 'start-execution':
                return HttpResponse('إجراء غير صالح', status=400)
            if not can_start:
                return HttpResponse('ليس لديك صلاحية بدء التنفيذ', status=403)
            try:
                project_id = UUID(request.POST.get('project_id', ''))
                client.post(f'/pm/projects/{project_id}/planning-status', data={'status': 'in_progress'})
            except (ForbiddenException, NotFoundException):
                raise
            except (ValueError, ConflictException, ApiException) as exc:
                request.execution_error = str(exc)
            else:
                return redirect(f'/pm/projects/{project_id}/work-orders/')

        project_rows = client.get('/pm/execution-center-projects')['items']
        completion_items = {}
        can_view_completion = allowed(identity, 'pm.completion.view')
        can_view_planning = allowed(identity, 'pm.planning.view')
        if can_view_completion:
            try:
                completion_items = {
                    item['id']: item for item in client.get('/pm/completion-center').get('items', [])
                }
            except (ForbiddenException, ApiException):
                # Completion is an optional capability for this navigation center.
                completion_items = {}
        projects = []
        for row in project_rows:
            project_id = UUID(row['id'])
            refs = client.get(
                f'/pm/projects/{project_id}/ui-references',
                params={'section': 'work-orders'},
            )
            project_data = refs['project']
            project_status = project_data.get('status', row.get('status', 'in_progress'))
            if project_status not in EXECUTION_CENTER_STATES:
                continue
            orders = client.get(f'/pm/projects/{project_id}/work-orders')['items'] \
                if project_status == 'in_progress' else []
            progress = execution_progress(refs.get('activities', []), orders) \
                if project_status == 'in_progress' else None
            order_stats = execution_order_stats(refs.get('activities', []), orders)
            completion = completion_items.get(str(project_id), {})
            ready_for_completion = bool(completion.get('ready_for_review'))
            needs_follow_up = bool(order_stats['follow_up'])
            client_name = project_data.get('client_name') or project_data.get('organization_name') or ''
            manager_name = project_data.get('manager_name') or 'غير محدد'
            projects.append({
                'id': str(project_id),
                'name': project_data['name'],
                'project_code': row.get('project_code', ''),
                'status': project_status,
                'status_label': PROJECT_STATES.get(project_status, project_status),
                'bucket': project_status,
                'buckets': ['all'] + ([project_status] if project_status in EXECUTION_CENTER_STATES else []) + ([
                    'follow_up'] if needs_follow_up else []) + (['ready_for_completion'] if ready_for_completion else []),
                'start_date': row.get('start_date') or '',
                'client_name': client_name,
                'manager_name': manager_name,
                'progress': progress,
                'order_stats': order_stats,
                'needs_follow_up': needs_follow_up,
                'ready_for_completion': ready_for_completion,
                'completion_href': f'/pm/completion/projects/{project_id}/' if ready_for_completion else '',
                'slides_href': f'/pm/projects/{project_id}/slides/' if can_view_planning else '',
                'href': f'/pm/projects/{project_id}/work-orders/',
                'results_href': f'/pm/projects/{project_id}/work-orders/?tab=results',
                'search_text': ' '.join([
                    project_data['name'], row.get('project_code', ''), client_name, manager_name,
                ]),
            })

        project_count = len(projects)
        bucket_counts = {
            'all': len(projects),
            'in_progress': sum(project['status'] == 'in_progress' for project in projects),
            'follow_up': sum(project['needs_follow_up'] for project in projects),
            'ready_for_completion': sum(project['ready_for_completion'] for project in projects),
        }
        active_bucket = 'all'
        return render(request, 'pm/execution_center.html', {
            'page_title': 'مركز التنفيذ', 'projects': projects,
            'project_count': project_count,
            'bucket_counts': bucket_counts,
            'active_bucket': active_bucket,
            'project_states': PROJECT_STATES,
            'execution_bucket_labels': EXECUTION_BUCKET_LABELS,
            'can_view_completion': can_view_completion,
            'can_view_planning': can_view_planning,
            'can_start': can_start,
            'execution_error': getattr(request, 'execution_error', ''),
        })
    except UnauthorizedException:
        return redirect('auth:login')
    except ForbiddenException:
        return HttpResponse('ليس لديك صلاحية لهذا القسم', status=403)
    except NotFoundException:
        return HttpResponse('المشروع غير متاح ضمن نطاقك', status=404)
    except ApiException:
        return HttpResponse('تعذر تحميل مركز التنفيذ؛ حاول مجددًا', status=503)
