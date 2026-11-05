"""Server-rendered adapters for scoped PM APIs. All changes are CSRF POSTs."""
import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from ..services.planning_display import cash_summary
from uuid import UUID
from django import forms
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods
from shared.services.api_client import ApiClient, ApiException, ForbiddenException, NotFoundException, UnauthorizedException
from ..services.planning import allowed
from ..services.operations import CONTROL, SECTIONS, STATUS, WEP_ACTION_LABELS, WO_NEXT, WEP_NEXT, next_consumption_code, next_risk_code, next_work_order_code, operation_form, payload


FORM_FIELD_SECTIONS = {
    'risks': [
        ('التعريف والارتباط', ('risk_code', 'level', 'phase_id', 'task_id', 'activity_id')),
        ('الوصف والتصنيف', ('description', 'classification')),
        ('التقييم', ('probability', 'impact', 'discovery_date')),
        ('المعالجة', ('corrective_action', 'owner_user_id')),
    ],
    'deviations': [
        ('التعريف والارتباط', ('deviation_code', 'level', 'phase_id', 'task_id', 'activity_id', 'deviation_type')),
        ('الأثر والمسؤولية', ('impact', 'responsible_user_id', 'target_date', 'causes')),
        ('الإجراء التصحيحي', ('description', 'corrective_action')),
    ],
    'cashflows': [
        ('تعريف البند والفترة', ('item_code', 'cash_flow_type', 'period')),
        ('القيمة والعملة', ('amount', 'currency', 'rate_date')),
        ('ملاحظات', ('notes',)),
    ],
    'communications': [
        ('تعريف خطة التواصل', ('item_code', 'report_type', 'purpose', 'frequency')),
        ('الأطراف والوسيلة', ('sender_user_id', 'receivers', 'mechanism')),
        ('ملاحظات', ('notes',)),
    ],
    'reports': [
        ('بيانات التقرير', ('report_code', 'report_date')),
        ('ملخص الأعمال والكميات', ('activities_count', 'planned_volume', 'executed_volume', 'work_hours')),
        ('الموارد والتكلفة', ('daily_cost', 'actual_workers', 'equipment_used', 'materials_used')),
        ('المشكلات والملاحظات', ('problems', 'notes')),
    ],
    'work-orders': [
        ('تعريف أمر التشغيل', ('work_order_code', 'activity_id')),
        ('التكليف والتاريخ', ('assignee_user_id', 'issue_date', 'planned_start_date')),
        ('ملاحظات التنفيذ', ('notes',)),
    ],
    'consumption': [
        ('تعريف المورد', ('consumption_code', 'item_name', 'item_type')),
        ('الكمية والتكلفة الفعلية', ('quantity', 'unit', 'unit_price', 'currency', 'rate_date')),
        ('المرجع', ('reference',)),
    ],
    'quantity': [('دفعة الإنجاز', ('quantity', 'notes'))],
    'update-order': [('بيانات الأمر قبل التنفيذ', ('assignee_user_id', 'issue_date', 'planned_start_date', 'notes'))],
    'reject': [('قرار الرفض', ('reason',))],
    'partial-close': [('قرار الإغلاق الجزئي', ('reason',))],
    'dependencies': [('طرفا العلاقة ونوعها', ('predecessor_id', 'successor_id', 'dependency_type'))],
}


def group_form_fields(form, kind):
    remaining = list(form.fields)
    groups = []
    for title, names in FORM_FIELD_SECTIONS.get(kind, ()):
        fields = [form[name] for name in names if name in remaining and name in form.fields]
        if fields:
            groups.append({'title': title, 'fields': fields})
            included = {field.name for field in fields}
            remaining = [name for name in remaining if name not in included]
    if remaining:
        groups.append({'title': 'بيانات إضافية', 'fields': [form[name] for name in remaining]})
    return groups


def url(project_id, section='', entity_id=None):
    base = f'/pm/projects/{UUID(str(project_id))}/'
    if section:
        base += section + '/'
    if entity_id:
        base += str(UUID(str(entity_id))) + '/'
    return base


def decimal_value(value):
    return Decimal(str(value or '0'))


def prepare_work_order_print_document(item, refs, project, events, consumptions, risks, can_view_risks):
    activities_by_id = {
        UUID(str(row['id'])).hex: row for row in refs.get('activities', [])
    }
    activity_id = UUID(str(item['activity_id'])).hex
    activity = activities_by_id.get(activity_id, {})
    users_by_id = {
        UUID(str(row['id'])).hex: row.get('name', '') for row in refs.get('users', [])
    }
    risk_owners = users_by_id
    print_risks = []
    if can_view_risks:
        for risk in risks:
            linked_activity_id = risk.get('activity_id')
            if (
                risk.get('level') != 'activity'
                or not linked_activity_id
                or UUID(str(linked_activity_id)).hex != activity_id
            ):
                continue
            print_risk = dict(risk)
            owner_id = risk.get('owner_user_id')
            print_risk['print_owner_name'] = (
                risk_owners.get(UUID(str(owner_id)).hex, '') if owner_id else ''
            )
            print_risk['print_status_label'] = STATUS.get(
                risk.get('status'), risk.get('status', 'غير محددة')
            )
            print_risks.append(print_risk)

    for event in events:
        if event.get('after_quantity') is None:
            event['after_quantity'] = event.get('after')
        if (
            event.get('after_quantity') is None
            and event.get('before_quantity') is not None
            and event.get('delta') is not None
        ):
            event['after_quantity'] = str(
                decimal_value(event['before_quantity']) + decimal_value(event['delta'])
            )

    planned_quantity = decimal_value(activity.get('planned_quantity'))
    actual_quantity = decimal_value(item.get('actual_quantity_snapshot'))
    assignee_id = item.get('assignee_user_id')
    return {
        'item': item,
        'events': events,
        'consumptions': consumptions,
        'print_activity': activity,
        'print_assignee': users_by_id.get(UUID(str(assignee_id)).hex, '') if assignee_id else '',
        'print_status_label': STATUS.get(item.get('status'), item.get('status', '')),
        'print_planned_quantity': str(planned_quantity),
        'print_actual_quantity': str(actual_quantity),
        'print_remaining_quantity': str(max(planned_quantity - actual_quantity, Decimal('0'))),
        'print_quantity_variance': str(actual_quantity - planned_quantity),
        'print_currency': project.get('currency', ''),
        'print_risks': print_risks,
        'can_view_risks': can_view_risks,
    }


def prepare_execution_rows(project_id, activities, orders, manage, project_status):
    activity_by_id = {UUID(row['id']).hex: dict(row) for row in activities}
    activity_orders = {key: [] for key in activity_by_id}
    for row in orders:
        activity_id = UUID(row['activity_id']).hex
        activity = activity_by_id.get(activity_id)
        row['href'] = url(project_id, 'work-orders', row['id'])
        row['status_label'] = STATUS.get(row.get('status'), row.get('status', ''))
        row['activity'] = activity
        row['activity_name'] = activity['name'] if activity else 'نشاط غير متاح'
        if activity is not None:
            activity_orders[activity_id].append(row)

    progress_values = []
    actual_cost = Decimal('0')
    for activity_id, activity in activity_by_id.items():
        related = activity_orders[activity_id]
        counted = [row for row in related if row.get('status') != 'rejected']
        planned = decimal_value(activity.get('planned_quantity'))
        actual = sum((decimal_value(row.get('actual_quantity_snapshot')) for row in counted), Decimal('0'))
        active_order = next(
            (row for row in related if row.get('status') in ('issued', 'in_progress')),
            None,
        )
        has_partial_close = any(bool(row.get('partial_close_reason')) for row in related)
        remaining = max(planned - actual, Decimal('0'))
        if project_status != 'in_progress':
            issue_block_reason = 'يظهر أمر الإصدار بعد بدء تنفيذ المشروع.'
        elif activity.get('approval_status') != 'approved':
            issue_block_reason = 'النشاط بانتظار الاعتماد أو لم يُعتمد بعد.'
        elif active_order is not None:
            issue_block_reason = 'يوجد أمر تشغيل نشط مرتبط بهذا النشاط.'
        elif has_partial_close:
            issue_block_reason = 'أُغلق النشاط جزئياً ولا يمكن إصدار أمر إضافي له.'
        elif planned <= 0:
            issue_block_reason = 'أدخل كمية مخططة للنشاط قبل إصدار أمر تشغيل.'
        elif remaining <= 0:
            issue_block_reason = 'اكتملت الكمية المخططة لهذا النشاط.'
        else:
            issue_block_reason = '' if manage else 'لا تملك صلاحية إصدار أمر تشغيل لهذا النشاط.'
        activity.update({
            'orders': related,
            'active_order': active_order,
            'actual_quantity': str(actual),
            'remaining_quantity': str(remaining),
            'progress_percent': min(round(actual * 100 / planned), 100) if planned > 0 else None,
            'over_plan': actual > planned if planned > 0 else False,
            'issue_block_reason': issue_block_reason,
            'show_in_unissued_orders': active_order is None and remaining > 0,
            'can_issue_order': bool(
                manage and project_status == 'in_progress'
                and activity.get('approval_status') == 'approved'
                and active_order is None and not has_partial_close
                and planned > 0 and remaining > 0
            ),
        })
        if planned > 0:
            progress_values.append(min(actual * 100 / planned, Decimal('100')))
        actual_cost += sum(
            (decimal_value(row.get('actual_cost')) for row in counted),
            Decimal('0'),
        )
    for row in orders:
        activity = activity_by_id.get(UUID(row['activity_id']).hex)
        planned = decimal_value(activity.get('planned_quantity')) if activity else Decimal('0')
        actual = decimal_value(row.get('actual_quantity_snapshot'))
        row['can_record_quantity'] = row.get('status') in ('issued', 'in_progress')
        row['progress_percent'] = min(round(actual * 100 / planned), 100) if planned > 0 else 0
        active = row.get('status') in ('issued', 'in_progress')
        partial = bool(row.get('partial_close_reason'))
        row['can_edit_order'] = bool(manage and row.get('status') == 'issued' and actual == 0
                                     and not row.get('approved_by'))
        row['can_record_quantity'] = bool(manage and active and actual < planned)
        row['can_consume'] = bool(manage and not row.get('approved_by')
                                  and (active or (partial and row.get('status') == 'closed')))
        row['can_partial_close'] = bool(manage and active and 0 < actual < planned)
        row['can_reject'] = bool(manage and active)
        row['can_approve'] = bool(manage and not row.get('approved_by') and actual > 0
                                  and ((partial and row.get('status') == 'closed' and actual < planned)
                                       or (not partial and row.get('status') == 'in_progress'
                                           and actual >= planned)))
    metrics = {
        'progress_percent': round(sum(progress_values, Decimal('0')) / len(progress_values))
        if progress_values else None,
        'active_orders': sum(row.get('status') in ('issued', 'in_progress') for row in orders),
        'actual_cost': str(actual_cost),
        'eligible_activities': sum(row['can_issue_order'] for row in activity_by_id.values()),
    }
    return list(activity_by_id.values()), metrics


def prepare_results_summary(activities, orders):
    """Build read-only presentation data from the already prepared execution rows.

    This deliberately keeps quantities at activity/unit level.  It does not
    introduce a second actual source or add quantities from Daily Work.
    """
    status_counts = {'complete': 0, 'active': 0, 'late': 0, 'blocked': 0}
    phase_groups = {}
    for activity in activities:
        progress = activity.get('progress_percent')
        if progress == 100:
            status = 'complete'
        elif activity.get('over_plan'):
            status = 'blocked'
        elif activity.get('active_order'):
            status = 'active'
        else:
            status = 'late'
        status_counts[status] += 1
        phase_name = activity.get('phase_name') or 'مرحلة غير محددة'
        group = phase_groups.setdefault(phase_name, {
            'name': phase_name, 'activities': 0, 'complete': 0,
            'active': 0, 'late': 0, 'blocked': 0,
        })
        group['activities'] += 1
        group[status] += 1
    phase_rows = []
    for group in phase_groups.values():
        # A phase percentage is intentionally not invented from mixed units.
        group['progress_available'] = False
        group['status_label'] = (
            'مكتملة' if group['complete'] == group['activities'] else
            'تحتاج متابعة' if group['late'] or group['blocked'] else
            'قيد التنفيذ' if group['active'] else 'لم تبدأ'
        )
        phase_rows.append(group)
    return {
        'status_counts': status_counts,
        'followup_count': status_counts['late'] + status_counts['blocked'],
        'phase_rows': phase_rows,
        'order_count': len(orders),
        'rejected_orders': sum(row.get('status') == 'rejected' for row in orders),
        'has_schedule': any(
            activity.get('planned_start_date') or activity.get('planned_end_date')
            for activity in activities
        ),
    }


def _schedule_date(value):
    """Return a presentation-only ISO date without manufacturing a forecast."""
    return str(value)[:10] if value else None


def _schedule_activity_key(value):
    try:
        return UUID(str(value)).hex
    except (TypeError, ValueError, AttributeError):
        return str(value or '').replace('-', '').lower()


def prepare_schedule_plan(activities, detail):
    """Join the immutable schedule-version forecast to execution actuals.

    The schedule remains the forecast source; progress stays derived from the
    existing WO quantity events prepared in ``prepare_execution_rows``.
    """
    schedule_items = {
        _schedule_activity_key(row.get('activity_id')): row
        for row in (detail or {}).get('items', [])
    }
    today = date.today().isoformat()
    rows, followups, upcoming = [], [], []
    counts = {'total': 0, 'complete': 0, 'active': 0, 'late': 0}
    for activity in activities:
        item = schedule_items.get(_schedule_activity_key(activity.get('id')))
        if not item:
            continue
        progress = activity.get('progress_percent')
        state = item.get('scheduling_state', '')
        finish = _schedule_date(item.get('early_finish'))
        start = _schedule_date(item.get('early_start'))
        blocked = state.startswith('blocked_')
        late = bool(finish and finish < today and progress != 100)
        if progress == 100:
            status, status_label = 'complete', 'مكتمل'
        elif blocked:
            status, status_label = 'blocked', 'محجوب'
        elif activity.get('active_order'):
            status, status_label = 'active', 'قيد التنفيذ'
        elif late:
            status, status_label = 'late', 'متأخر'
        else:
            status, status_label = 'planned', 'مجدول'
        duration = item.get('remaining_work_minutes')
        row = dict(activity)
        row.update({
            'schedule_start': start,
            'schedule_finish': finish,
            'schedule_duration_days': round(float(duration) / 60 / 8, 1) if duration is not None else None,
            'schedule_status': status,
            'schedule_status_label': status_label,
            'schedule_critical': bool(item.get('is_critical')),
            'schedule_reason': item.get('block_reason') or (
                'تجاوز تاريخ النهاية المتوقع دون اكتمال فعلي.' if late else ''
            ),
        })
        rows.append(row)
        counts['total'] += 1
        if status == 'complete':
            counts['complete'] += 1
        elif status == 'active':
            counts['active'] += 1
        elif status in ('late', 'blocked'):
            counts['late'] += 1
            followups.append(row)
        if status not in ('complete', 'blocked') and start and start >= today:
            upcoming.append(row)
    rows.sort(key=lambda row: row.get('schedule_start') or '9999-12-31')
    upcoming.sort(key=lambda row: row.get('schedule_start') or '9999-12-31')
    return {
        'rows': rows,
        'followups': followups,
        'upcoming': upcoming[:5],
        'counts': counts,
        'project_start': min((row['schedule_start'] for row in rows if row.get('schedule_start')), default=None),
        'project_finish': max((row.get('schedule_finish') or '' for row in rows), default='') or None,
    }


def prepare_schedule_setup(activities, detail, baseline_detail, dependencies, daily_items,
                           readiness_date=None):
    """Build the preparation review without creating a new planning truth.

    Membership comes from the immutable approved Baseline snapshot. Schedule
    dates come from the official schedule version when one exists. Readiness
    and blockers are shown only when Daily Work has an item for today's
    explicitly requested date; absence stays ``unavailable``.
    """
    current = {_schedule_activity_key(row.get('id')): row for row in activities}
    schedule_items = {
        _schedule_activity_key(row.get('activity_id')): row
        for row in (detail or {}).get('items', [])
    }
    baseline_rows = [
        row for row in (baseline_detail or {}).get('items', [])
        if row.get('entity_kind') == 'activities'
    ]
    dependency_rows = list(dependencies or [])
    daily_by_activity = {}
    for item in daily_items or []:
        daily_by_activity.setdefault(_schedule_activity_key(item.get('activity_id')), []).append(item)

    rows = []
    for baseline_row in baseline_rows:
        key = _schedule_activity_key(baseline_row.get('entity_id'))
        activity = dict(current.get(key) or {})
        try:
            snapshot = json.loads(baseline_row.get('snapshot') or '{}')
        except (TypeError, ValueError):
            snapshot = {}
        activity.setdefault('id', baseline_row.get('entity_id'))
        activity.setdefault('activity_code', baseline_row.get('code') or '')
        activity.setdefault('name', baseline_row.get('name') or 'نشاط غير متاح')
        activity.setdefault('planned_duration', snapshot.get('planned_duration'))
        activity.setdefault('planned_start_date', snapshot.get('planned_start_date'))
        activity.setdefault('planned_end_date', snapshot.get('planned_end_date'))
        schedule = schedule_items.get(key) or {}
        linked_daily = daily_by_activity.get(key, [])
        blockers = [
            blocker for item in linked_daily for blocker in item.get('blockers', [])
            if blocker.get('status', 'open') == 'open'
        ]
        readiness_values = [item.get('readiness_status') for item in linked_daily]
        if blockers or 'not_ready' in readiness_values:
            readiness, readiness_label = 'not-ready', 'غير جاهز'
        elif linked_daily and readiness_values and all(value == 'ready' for value in readiness_values):
            readiness, readiness_label = 'ready', 'جاهز'
        elif linked_daily:
            readiness, readiness_label = 'warning', 'بحاجة إلى تحقق'
        else:
            readiness, readiness_label = 'unavailable', 'غير مسجلة'
        incoming = [
            row for row in dependency_rows
            if _schedule_activity_key(row.get('successor_id')) == key
        ]
        outgoing = [
            row for row in dependency_rows
            if _schedule_activity_key(row.get('predecessor_id')) == key
        ]
        duration_minutes = schedule.get('remaining_work_minutes')
        duration_days = (
            round(float(duration_minutes) / 60 / 8, 1)
            if duration_minutes is not None else activity.get('planned_duration')
        )
        blocked = str(schedule.get('scheduling_state') or '').startswith('blocked_')
        activity.update({
            'setup_start': _schedule_date(schedule.get('early_start')) or activity.get('planned_start_date'),
            'setup_finish': _schedule_date(schedule.get('early_finish')) or activity.get('planned_end_date'),
            'setup_duration_days': duration_days,
            'setup_readiness': readiness,
            'setup_readiness_label': readiness_label,
            'setup_blockers': blockers,
            'setup_dependencies': incoming,
            'setup_successors': outgoing,
            'setup_dependency_types': ', '.join(sorted({row.get('dependency_type', '') for row in incoming if row.get('dependency_type')})),
            'setup_blocked': blocked,
            'setup_block_reason': schedule.get('block_reason') or '',
            'setup_critical': bool(schedule.get('is_critical')),
        })
        rows.append(activity)
    return {
        'rows': rows,
        'counts': {
            'total': len(rows),
            'ready': sum(row['setup_readiness'] == 'ready' for row in rows),
            'blockers': sum(len(row['setup_blockers']) for row in rows),
            'incomplete': sum(row['setup_blocked'] for row in rows),
            'unavailable': sum(row['setup_readiness'] == 'unavailable' for row in rows),
        },
        'project_start': min((str(row['setup_start'])[:10] for row in rows if row.get('setup_start')), default=None),
        'project_finish': max((str(row['setup_finish'])[:10] for row in rows if row.get('setup_finish')), default=None),
        'critical_count': sum(row['setup_critical'] for row in rows),
        'dependency_count': len(dependency_rows),
        'readiness_date': readiness_date or date.today().isoformat(),
    }


def _schedule_finish(detail):
    """Return a date only when the immutable schedule items provide one."""
    values = [_schedule_date(row.get('early_finish')) for row in (detail or {}).get('items', [])]
    return max((value for value in values if value), default=None)


def _schedule_variance_days(approved_finish, proposed_finish):
    """Compare two published dates without manufacturing dates for missing inputs."""
    if not approved_finish or not proposed_finish:
        return None
    try:
        return (date.fromisoformat(proposed_finish) - date.fromisoformat(approved_finish)).days
    except ValueError:
        return None


def prepare_forecast_presentation(activities, approved_detail, proposed_detail, impact):
    """Merge only read models for the execution-plan presentation.

    Forecast dates and quantities come from immutable schedule versions.  The
    reconciliation adapter supplies WO/WEP/Daily readiness references and
    remains the only place that reads their cross-module relationship.
    """
    approved_items = {
        _schedule_activity_key(row.get('activity_id')): row
        for row in (approved_detail or {}).get('items', [])
    }
    proposed_items = {
        _schedule_activity_key(row.get('activity_id')): row
        for row in (proposed_detail or {}).get('items', [])
    }
    impact_items = {
        _schedule_activity_key(row.get('activity_id')): row
        for row in (impact or {}).get('items', [])
    }
    rows = []
    for activity in activities:
        key = _schedule_activity_key(activity.get('id'))
        proposed = proposed_items.get(key)
        approved = approved_items.get(key)
        source = proposed or approved
        if not source:
            continue
        projection = impact_items.get(key, {})
        forecast = projection.get('forecast', source)
        actual = projection.get('actual', {})
        rows.append({
            **activity,
            'forecast_start': _schedule_date(forecast.get('early_start')),
            'forecast_finish': _schedule_date(forecast.get('early_finish')),
            'approved_finish': _schedule_date((projection.get('approved_forecast') or approved or {}).get('early_finish')),
            'remaining_quantity': forecast.get('remaining_quantity'),
            'actual_quantity': actual.get('actual_quantity', forecast.get('actual_quantity_at_measurement')),
            'forecast_unit': actual.get('unit') or activity.get('unit'),
            'forecast_critical': bool(forecast.get('is_critical', source.get('is_critical'))),
            'classification': projection.get('classification', 'unavailable' if proposed_detail and not impact else 'aligned'),
            'reasons': projection.get('reasons', []),
            'work_order_count': len(projection.get('work_orders', [])),
            'weekly_commitment_count': len(projection.get('weekly_commitments', [])),
            'daily_work_count': len(projection.get('daily_work', [])),
        })
    rows.sort(key=lambda row: row.get('forecast_start') or '9999-12-31')
    counts = {name: sum(row['classification'] == name for row in rows)
              for name in ('aligned', 'needs_review', 'delayed', 'unavailable')}
    return {'rows': rows, 'counts': counts}


@require_http_methods(['GET'])
def workspace(request,section):
    if section not in SECTIONS:
        raise Http404
    client=ApiClient(token=request.session.get('access_token'))
    try:
        client.get('/pm/')
        identity=client.get('/auth/me')
        request.core_identity=identity
        request.core_modules=client.get('/modules')
        rows=client.get('/pm/ui-projects',params={'section':section})['items']
        for row in rows:
            row['href']=url(row['id'],section)
        return render(request,'pm/operation_projects.html',{'label':SECTIONS[section][0],'rows':rows})
    except UnauthorizedException:
        return redirect('auth:login')
    except ForbiddenException:
        return HttpResponse('ليس لديك صلاحية لهذا القسم',status=403)
    except ApiException:
        return HttpResponse('تعذر الاتصال بالخدمة؛ حاول مجددًا',status=503)


@require_http_methods(['GET','POST'])
def operations(request, project_id, section, entity_id=None, action=None):
    if section not in SECTIONS or (action and section not in CONTROL):
        raise Http404
    label, view_permission, manage_permission = SECTIONS[section]
    client = ApiClient(token=request.session.get('access_token'))
    base = f'/pm/projects/{project_id}/{section}'
    endpoint = base + (f'/{entity_id}' if entity_id else '')
    try:
        client.get('/pm/')
        identity = client.get('/auth/me')
        request.core_identity = identity
        request.core_modules = client.get('/modules')
        if not allowed(identity,view_permission):
            return HttpResponse('ليس لديك صلاحية العرض',status=403)
        refs = client.get(f'/pm/projects/{project_id}/ui-references',params={'section':section})
        manage = allowed(identity,manage_permission)
        item = client.get(endpoint) if entity_id else None
        project = dict(refs['project'])
        if section == 'risks':
            try:
                project.update(client.get(f'/pm/projects/{project_id}'))
            except ApiException:
                pass
            organization_names = {
                str(row.get('id')): row.get('name', '')
                for row in refs.get('organizations', [])
            }
            project['organization_name'] = (
                project.get('organization_name') or
                organization_names.get(str(project.get('organization_id')), '')
            )
        project['status_label'] = STATUS.get(project.get('status'), project.get('status', 'غير محددة'))
        project['organization_name'] = (
            project.get('organization_name') or project.get('organization') or
            project.get('client_name') or 'غير محدد'
        )
        project['manager_name'] = project.get('manager_name') or 'غير محدد'
        project['project_type'] = project.get('project_type') or project.get('type') or 'غير محدد'
        project['location'] = project.get('location') or project.get('site_location') or 'غير محدد'
        ctx = {'page_title':label,'label':label,'project':project, 'back':url(project_id,section),
               'project_url':url(project_id), 'item':item, 'section':section,'action':action, 'manage':manage,
               'open_action': request.GET.get('open_action', ''),
               'navigation':[{'label':v[0],'url':url(project_id,k),'active':k==section} for k,v in SECTIONS.items() if allowed(identity,v[1])]}
        if section == 'work-orders' and entity_id and request.GET.get('fx') == '1':
            if not manage:
                return HttpResponse('ليس لديك صلاحية معاينة تكلفة التنفيذ', status=403)
            quote = client.get(f'/pm/projects/{project_id}/execution-rate', params={
                'source': request.GET.get('currency', ''),
                'rate_date': request.GET.get('rate_date', ''),
                'quantity': request.GET.get('quantity', ''),
                'unit_price': request.GET.get('unit_price', ''),
            })
            return JsonResponse(quote)
        ctx['wep_list_url'] = url(project_id, 'weekly-plans')
        ctx['wep_create_url'] = url(project_id, 'weekly-plans') + '?create=1'
        ctx['wep_create_action'] = url(project_id, 'weekly-plans')
        ctx['wep_selected_url'] = url(project_id, 'weekly-plans', entity_id) if entity_id else ctx['wep_list_url']
        if section == 'weekly-plans':
            plans = client.get(base)['items']
            ctx['week_choices'] = [dict(plan, href=url(project_id, section, plan['id']),
                                        selected=bool(entity_id and UUID(plan['id']) == entity_id),
                                        status_label=STATUS.get(plan['status'], plan['status']))
                                   for plan in plans]
            ctx['candidate_activities'] = refs['activities']
        form_refs = refs
        if section == 'work-orders':
            execution_orders = client.get(base)['items']
            activities, metrics = prepare_execution_rows(
                project_id, refs['activities'], execution_orders, manage,
                refs['project'].get('status'),
            )
            activity_by_id = {UUID(row['id']).hex: row for row in activities}
            ctx.update({
                'activities': activities,
                'eligible_activities': [
                    row for row in activities if row.get('can_issue_order')
                ],
                'unissued_activities': [
                    row for row in activities if row.get('show_in_unissued_orders')
                ],
                'orders': execution_orders,
                'execution_metrics': metrics,
                'project_status_label': STATUS.get(
                    refs['project'].get('status'),
                    refs['project'].get('status', 'غير محددة'),
                ),
                'can_view_risks': allowed(identity, 'pm.risks.view'),
                'can_view_deviations': allowed(identity, 'pm.planning.view'),
                'can_view_reports': allowed(identity, 'pm.reports.view'),
                'can_view_completion': allowed(identity, 'pm.completion.view'),
                'completion_review_url': (
                    f'/pm/completion/projects/{project_id}/'
                    if allowed(identity, 'pm.completion.view') else None
                ),
                'completion_review_ready': bool(
                    decimal_value(metrics.get('progress_percent')) >= Decimal('100')
                    and refs['project'].get('status') != 'closed'
                    and allowed(identity, 'pm.completion.view')
                ),
                'risks': [],
                'deviations': [],
            })
            ctx['results_summary'] = prepare_results_summary(activities, execution_orders)
            ctx.update({
                'can_view_schedule': allowed(identity, 'pm.schedule.view'),
                # Closed projects remain readable in this workspace. The UI route
                # does not expose lifecycle writes for them even to privileged users.
                'schedule_read_only': refs['project'].get('status') == 'closed',
                'can_manage_schedule': (
                    refs['project'].get('status') != 'closed'
                    and allowed(identity, 'pm.schedule.manage')
                ),
                'can_propose_schedule': (
                    refs['project'].get('status') != 'closed'
                    and allowed(identity, 'pm.schedule.propose')
                ),
                'can_approve_schedule': (
                    refs['project'].get('status') != 'closed'
                    and allowed(identity, 'pm.schedule.approve')
                ),
                'schedule_versions': [],
                'schedule_selected': None,
                'schedule_detail': None,
                'schedule_approved': None,
                'schedule_approved_detail': None,
                'schedule_proposed': None,
                'schedule_proposed_detail': None,
                'execution_plan_mode': 'setup',
                'schedule_setup_baseline': None,
                'schedule_setup_baseline_detail': None,
                'schedule_dependencies': [],
                'schedule_dependencies_available': False,
                'schedule_dependencies_unavailable': False,
                'schedule_setup': {'rows': [], 'counts': {'total': 0, 'ready': 0, 'blockers': 0, 'incomplete': 0, 'unavailable': 0}},
                'schedule_impact': None,
                'schedule_impact_unavailable': False,
                'forecast_presentation': {'rows': [], 'counts': {
                    'aligned': 0, 'needs_review': 0, 'delayed': 0, 'unavailable': 0}},
                'schedule_comparison': {'approved_finish': None, 'proposed_finish': None, 'variance_days': None},
                'schedule_plan': {'rows': [], 'followups': [], 'upcoming': [], 'project_start': None, 'project_finish': None,
                                  'counts': {'total': 0, 'complete': 0, 'active': 0, 'late': 0}},
                'schedule_baselines': [],
            })
            if ctx['can_view_schedule']:
                ctx['schedule_versions'] = client.get(
                    f'/pm/projects/{project_id}/schedule-versions'
                ).get('items', [])
                ctx['schedule_approved'] = next(
                    (row for row in ctx['schedule_versions'] if row.get('status') == 'approved'), None)
                ctx['schedule_proposed'] = next(
                    (row for row in ctx['schedule_versions']
                     if row.get('status') in ('proposed', 'draft')), None)
                # An approved version always keeps the tab in follow-up mode. A newer
                # draft remains reviewable beside it and never becomes execution truth.
                ctx['execution_plan_mode'] = 'followup' if ctx['schedule_approved'] else 'setup'
                ctx['schedule_selected'] = ctx['schedule_proposed'] or ctx['schedule_approved']
                if ctx['schedule_approved']:
                    ctx['schedule_approved_detail'] = client.get(
                        f"/pm/projects/{project_id}/schedule-versions/{ctx['schedule_approved']['id']}"
                    )
                    ctx['schedule_approved'] = ctx['schedule_approved_detail'].get(
                        'version', ctx['schedule_approved'])
                if ctx['schedule_proposed']:
                    ctx['schedule_proposed_detail'] = client.get(
                        f"/pm/projects/{project_id}/schedule-versions/{ctx['schedule_proposed']['id']}"
                    )
                    ctx['schedule_proposed'] = ctx['schedule_proposed_detail'].get(
                        'version', ctx['schedule_proposed'])
                    if ctx['schedule_proposed'].get('actual_as_of'):
                        try:
                            ctx['schedule_impact'] = client.get(
                                f"/pm/projects/{project_id}/schedule-versions/{ctx['schedule_proposed']['id']}/execution-impact"
                            )
                        except ApiException:
                            # The adapter is permission-scoped; absence of one source must
                            # not be shown as zero WO, WEP, or Daily Work information.
                            ctx['schedule_impact_unavailable'] = True
                if ctx['schedule_selected']:
                    ctx['schedule_detail'] = (
                        ctx['schedule_proposed_detail'] if ctx['schedule_proposed']
                        else ctx['schedule_approved_detail'])
                    ctx['schedule_plan'] = prepare_schedule_plan(
                        activities, ctx['schedule_detail'],
                    )
                ctx['forecast_presentation'] = prepare_forecast_presentation(
                    activities, ctx['schedule_approved_detail'], ctx['schedule_proposed_detail'],
                    ctx['schedule_impact'])
                approved_finish = _schedule_finish(ctx['schedule_approved_detail'])
                proposed_finish = _schedule_finish(ctx['schedule_proposed_detail'])
                ctx['schedule_comparison'] = {
                    'approved_finish': approved_finish,
                    'proposed_finish': proposed_finish,
                    'variance_days': _schedule_variance_days(approved_finish, proposed_finish),
                }
            if ctx['can_view_schedule'] and allowed(identity, 'pm.planning.view'):
                try:
                    ctx['schedule_baselines'] = client.get(
                        f'/pm/projects/{project_id}/baselines'
                    ).get('items', [])
                except ApiException:
                    # The create endpoint will still give the authoritative reason;
                    # do not make the execution workspace unavailable for this list.
                    ctx['schedule_baselines'] = []
            if allowed(identity, 'pm.planning.view'):
                try:
                    ctx['schedule_dependencies'] = client.get(
                        f'/pm/projects/{project_id}/dependencies'
                    ).get('items', [])
                    ctx['schedule_dependencies_available'] = True
                except ApiException:
                    ctx['schedule_dependencies_unavailable'] = True
                baseline_id = (
                    (ctx['schedule_selected'] or {}).get('baseline_id')
                    or ((ctx['schedule_baselines'][0].get('id')) if ctx['schedule_baselines'] else None)
                )
                if baseline_id:
                    try:
                        ctx['schedule_setup_baseline_detail'] = client.get(
                            f'/pm/projects/{project_id}/baselines/{baseline_id}'
                        )
                        ctx['schedule_setup_baseline'] = ctx['schedule_setup_baseline_detail'].get('baseline')
                    except ApiException:
                        ctx['schedule_setup_baseline_detail'] = None
            daily_date = request.GET.get('daily_date') or date.today().isoformat()
            try:
                daily_items = client.get(
                    f'/daily-work/projects/{project_id}/items',
                    params={'work_date': daily_date},
                ).get('items', [])
            except ApiException:
                daily_items = []
            daily_user_names = {
                str(user.get('id', '')).replace('-', '').lower():
                    user.get('name') or user.get('username') or 'مستخدم غير متاح'
                for user in refs.get('users', [])
            }
            for daily in daily_items:
                assignee_id = str(daily.get('assignee_user_id') or '').replace('-', '').lower()
                daily['assignee_name'] = daily_user_names.get(assignee_id, 'غير معيّن')
                order = next((row for row in execution_orders
                              if str(row.get('id', '')).replace('-', '').lower() ==
                              str(daily.get('work_order_id') or '').replace('-', '').lower()), None)
                daily['work_order_code'] = order.get('work_order_code', '') if order else ''
            ctx['schedule_setup'] = prepare_schedule_setup(
                activities,
                ctx.get('schedule_detail'),
                ctx.get('schedule_setup_baseline_detail'),
                ctx.get('schedule_dependencies'),
                daily_items,
                readiness_date=daily_date,
            )
            ctx.update({
                'daily_date': daily_date,
                'daily_items': daily_items,
                'daily_users': refs.get('users', []),
                'can_manage_daily_work': allowed(identity, 'daily_work.manage'),
            })
            ctx['can_view_wep'] = allowed(identity, 'pm.wep.view')
            ctx['can_manage_wep'] = allowed(identity, 'pm.wep.manage')
            ctx['wep_plans'] = []
            ctx['wep_selected'] = None
            ctx['wep_items'] = []
            ctx['wep_users'] = []
            ctx['wep_candidates'] = activities
            ctx['wep_mode'] = 'planning'
            ctx['wep_daily_contract_available'] = allowed(identity, 'daily_work.view')
            if ctx['can_view_wep']:
                ctx['wep_users'] = refs.get('users', [])
                ctx['wep_plans'] = client.get(f'/pm/projects/{project_id}/weekly-plans')['items']
                selected_plan_id = request.GET.get('weekly_plan_id')
                selected_plan = next(
                    (plan for plan in ctx['wep_plans'] if selected_plan_id and plan['id'] == selected_plan_id),
                    None,
                ) or (ctx['wep_plans'][-1] if ctx['wep_plans'] else None)
                if selected_plan:
                    ctx['wep_selected'] = client.get(
                        f'/pm/projects/{project_id}/weekly-plans/{selected_plan["id"]}'
                    )
                    ctx['wep_items'] = ctx['wep_selected'].get('items', [])
                planned_ids = {row['activity_id'] for row in ctx['wep_items']}
                ctx['wep_user_names'] = {
                    UUID(str(user['id'])).hex: user.get('name') or user.get('username') or 'مستخدم'
                    for user in refs.get('users', [])
                    if user.get('id')
                }
                for activity in ctx['wep_candidates']:
                    activity['wep_item'] = next(
                        (row for row in ctx['wep_items'] if row['activity_id'] == activity['id']), None
                    )
                    activity['wep_planned'] = activity['id'] in planned_ids
                    if activity['wep_item']:
                        assignee_id = activity['wep_item'].get('assignee_user_id')
                        activity['wep_item']['assignee_name'] = ctx['wep_user_names'].get(
                            UUID(str(assignee_id)).hex, 'غير معيّن'
                        ) if assignee_id else 'غير معيّن'
                if ctx['wep_selected']:
                    ctx['wep_selected']['status_label'] = STATUS.get(
                        ctx['wep_selected'].get('status'), ctx['wep_selected'].get('status', '')
                    )
                    ctx['wep_selected_url'] = url(project_id, 'weekly-plans', ctx['wep_selected']['id'])
                    selected_index = next(
                        (index for index, plan in enumerate(ctx['wep_plans'])
                         if plan['id'] == ctx['wep_selected']['id']), 0,
                    )
                    ctx['wep_previous'] = ctx['wep_plans'][selected_index - 1] if selected_index > 0 else None
                    ctx['wep_next'] = (
                        ctx['wep_plans'][selected_index + 1]
                        if selected_index + 1 < len(ctx['wep_plans']) else None
                    )
                    ctx['wep_mode'] = (
                        'followup' if ctx['wep_selected'].get('status') in ('approved', 'in_progress', 'closed')
                        else 'planning'
                    )

                    daily_by_activity = {}
                    if ctx['wep_daily_contract_available']:
                        try:
                            week_start = date.fromisoformat(ctx['wep_selected']['start_date'])
                            week_end = date.fromisoformat(ctx['wep_selected']['end_date'])
                            # WEP is weekly by contract. The cap prevents malformed legacy
                            # periods from expanding into an unbounded set of API reads.
                            day_count = min(max((week_end - week_start).days + 1, 0), 31)
                            for offset in range(day_count):
                                work_date = (week_start + timedelta(days=offset)).isoformat()
                                for daily in client.get(
                                    f'/daily-work/projects/{project_id}/items',
                                    params={'work_date': work_date},
                                ).get('items', []):
                                    daily_by_activity.setdefault(daily.get('activity_id'), []).append(daily)
                        except (ApiException, TypeError, ValueError):
                            ctx['wep_daily_contract_available'] = False

                    activity_map = {activity['id']: activity for activity in ctx['wep_candidates']}
                    quantity_totals = {}
                    missing_data = 0
                    met_count = 0
                    open_blockers = 0
                    ready_count = 0
                    week_has_ended = date.today() > date.fromisoformat(ctx['wep_selected']['end_date'])
                    for row in ctx['wep_items']:
                        activity = activity_map.get(row.get('activity_id'), {})
                        target = decimal_value(row.get('weekly_target', row.get('target')))
                        actual = decimal_value(row.get('actual'))
                        remaining = max(target - actual, Decimal('0'))
                        unit = activity.get('unit') or 'غير محددة'
                        quantity_totals[unit] = quantity_totals.get(unit, Decimal('0')) + target
                        linked_daily = daily_by_activity.get(row.get('activity_id'), [])
                        blockers = [
                            blocker for daily in linked_daily
                            for blocker in daily.get('blockers', [])
                            if blocker.get('status', 'open') == 'open'
                        ]
                        readiness_values = [daily.get('readiness_status') for daily in linked_daily]
                        if blockers or 'not_ready' in readiness_values:
                            readiness_status, readiness_label = 'not-ready', 'غير جاهز'
                        elif linked_daily and readiness_values and all(value == 'ready' for value in readiness_values):
                            readiness_status, readiness_label = 'ready', 'جاهز'
                            ready_count += 1
                        elif linked_daily:
                            readiness_status, readiness_label = 'warning', 'بحاجة إلى تحقق'
                        else:
                            readiness_status, readiness_label = 'unavailable', 'غير مسجلة'
                        orders = activity.get('orders') or []
                        linked_order = activity.get('active_order') or (orders[-1] if orders else None)
                        achievement = round(actual * 100 / target) if target > 0 else 0
                        commitment_met = bool(target > 0 and actual >= target)
                        if commitment_met:
                            activity_state, activity_state_label = 'complete', 'مكتمل'
                        elif ctx['wep_selected'].get('status') == 'closed' or week_has_ended:
                            activity_state, activity_state_label = 'delayed', 'متأخر'
                        elif ctx['wep_selected'].get('status') == 'approved':
                            activity_state, activity_state_label = 'approved', 'معتمد'
                        elif ctx['wep_mode'] == 'followup':
                            activity_state, activity_state_label = 'progress', 'قيد التنفيذ'
                        else:
                            activity_state, activity_state_label = 'planned', 'مخطط'
                        met_count += int(commitment_met)
                        open_blockers += len(blockers)
                        if not activity or not activity.get('unit') or row.get('undated_actual'):
                            missing_data += 1
                        row.update({
                            'activity_name': activity.get('name', 'نشاط غير متاح'),
                            'activity_code': activity.get('activity_code', ''),
                            'phase_name': activity.get('phase_name', 'مرحلة غير محددة'),
                            'task_name': activity.get('task_name', ''),
                            'unit': unit,
                            'target_display': str(target),
                            'actual_display': str(actual),
                            'remaining_display': str(remaining),
                            'achievement_percent': achievement,
                            'commitment_met': commitment_met,
                            'activity_state': activity_state,
                            'activity_state_label': activity_state_label,
                            'readiness_status': readiness_status,
                            'readiness_label': readiness_label,
                            'readiness_items': linked_daily,
                            'blockers': blockers,
                            'linked_order': linked_order,
                            'assignee_name': ctx['wep_user_names'].get(
                                UUID(str(row['assignee_user_id'])).hex, 'غير معيّن'
                            ) if row.get('assignee_user_id') else 'غير معيّن',
                        })
                    planned_items = list(ctx['wep_items'])
                    closure = None
                    if ctx['wep_selected'].get('closure'):
                        try:
                            closure = json.loads(ctx['wep_selected']['closure'])
                        except (TypeError, ValueError):
                            closure = None
                    ppc = closure.get('ppc') if closure else (
                        str(round(Decimal(met_count) * 100 / len(planned_items), 4))
                        if planned_items else None
                    )
                    ctx['wep_metrics'] = {
                        'planned_items': len(planned_items),
                        'ready_items': ready_count,
                        'readiness_known': sum(bool(row['readiness_items']) for row in planned_items),
                        'linked_orders': sum(bool(row['linked_order']) for row in planned_items),
                        'blocked_items': open_blockers,
                        'missing_data': missing_data,
                        'met_items': met_count,
                        'unmet_items': max(len(planned_items) - met_count, 0),
                        'ppc': ppc,
                        'ppc_final': bool(closure),
                        'quantity_totals': [
                            {'unit': unit, 'value': str(value)}
                            for unit, value in sorted(quantity_totals.items())
                        ],
                        'mixed_units': len(quantity_totals) > 1,
                    }
                    targets = WEP_NEXT.get(ctx['wep_selected'].get('status'), [])
                    if ctx['wep_selected'].get('carried_over'):
                        targets = [target for target in targets if target != 'reopened']
                    ctx['wep_transitions'] = (
                        [{'value': target, 'label': WEP_ACTION_LABELS.get(target, STATUS[target])} for target in targets]
                        if ctx['can_manage_wep'] else []
                    )
                    primary_targets = [target for target in targets if target not in ('cancelled', 'reopened', 'draft')]
                    ctx['wep_primary_transition'] = (
                        {'value': primary_targets[0], 'label': WEP_ACTION_LABELS.get(primary_targets[0], STATUS[primary_targets[0]])}
                        if primary_targets and ctx['can_manage_wep'] else None
                    )
                    ctx['wep_secondary_transitions'] = [
                        transition for transition in ctx['wep_transitions']
                        if not ctx['wep_primary_transition']
                        or transition['value'] != ctx['wep_primary_transition']['value']
                    ]
                    ctx['wep_addable_candidates'] = [
                        activity for activity in ctx['wep_candidates']
                        if not activity.get('wep_item') and activity.get('approval_status') == 'approved'
                    ]
                else:
                    ctx['wep_metrics'] = {
                        'planned_items': 0, 'ready_items': 0, 'readiness_known': 0,
                        'linked_orders': 0, 'blocked_items': 0, 'missing_data': 0,
                        'met_items': 0, 'unmet_items': 0, 'ppc': None,
                        'ppc_final': False, 'quantity_totals': [], 'mixed_units': False,
                    }
            ctx['selected_activity'] = (
                activity_by_id.get(UUID(item['activity_id']).hex)
                if item else next(iter(activities), None)
            )
            ctx['can_create_work_order'] = metrics['eligible_activities'] > 0
            if refs['project'].get('status') != 'in_progress':
                ctx['execution_block_reason'] = (
                    'لا يمكن إصدار أمر تشغيل قبل اعتماد الخطة وبدء تنفيذ المشروع.'
                )
            elif any(row.get('approval_status') != 'approved' for row in activities):
                ctx['execution_block_reason'] = (
                    'لا يمكن إصدار أمر تشغيل قبل إقرار النشاط ضمن الخطة المعتمدة.'
                )
            else:
                ctx['execution_block_reason'] = (
                    'لا توجد أنشطة مستوفية حالياً؛ راجع بطاقات الأنشطة أدناه لمعرفة شروط الإصدار.'
                )
            form_refs = dict(refs, activities=[
                {'id':row['id'], 'name':row['name']}
                for row in activities if row['can_issue_order']
            ])
            if ctx['can_view_risks']:
                ctx['risks'] = client.get(f'/pm/projects/{project_id}/risks')['items']
                ctx['open_risk_count'] = sum(row.get('status') == 'active' for row in ctx['risks'])
            if ctx['can_view_deviations']:
                ctx['deviations'] = client.get(f'/pm/projects/{project_id}/deviations')['items']
                ctx['open_deviation_count'] = sum(row.get('status') == 'open' for row in ctx['deviations'])
            if item:
                planned = decimal_value(
                    (ctx['selected_activity'] or {}).get('planned_quantity'),
                )
                actual = decimal_value(item.get('actual_quantity_snapshot'))
                partial_close = bool(item.get('partial_close_reason'))
                ctx['can_consume'] = bool(
                    manage and not item.get('approved_by') and item.get('status') != 'rejected'
                    and (item.get('status') in ('issued', 'in_progress')
                         or (partial_close and item.get('status') == 'closed'))
                )
                ctx['can_approve'] = bool(
                    manage and not item.get('approved_by') and actual > 0
                    and ((partial_close and item.get('status') == 'closed' and actual < planned)
                         or (not partial_close and item.get('status') == 'in_progress' and actual >= planned))
                )
                ctx['can_reject'] = bool(manage and item.get('status') in ('issued', 'in_progress'))
                ctx['can_partial_close'] = bool(
                    manage and item.get('status') in ('issued', 'in_progress') and 0 < actual < planned
                )
                ctx['can_edit_order'] = bool(
                    manage and item.get('status') == 'issued' and actual == 0
                    and not item.get('approved_by')
                )
                user_names = {str(row['id']).replace('-', '').lower(): row.get('name', '')
                              for row in refs.get('users', [])}
                ctx['approved_by_name'] = user_names.get(str(item.get('approved_by') or '').replace('-', '').lower(), '')
                ctx['rejected_by_name'] = user_names.get(str(item.get('rejected_by') or '').replace('-', '').lower(), '')
                ctx['partial_closed_by_name'] = user_names.get(
                    str(item.get('partial_closed_by') or '').replace('-', '').lower(), '')
                ctx['consumption_unavailable'] = not ctx['can_consume']
        form = None
        risk_rows = None
        command = request.POST.get('command','') if request.method=='POST' else ''
        if section == 'work-orders' and command.startswith('schedule_'):
            schedule_id = request.POST.get('schedule_version_id', '')
            schedule_base = f'/pm/projects/{project_id}/schedule-versions'
            try:
                if command == 'schedule_recalculate_actual':
                    if not ctx.get('can_manage_schedule'):
                        return HttpResponse('ليس لديك صلاحية إعادة حساب إصدار الجدولة.', status=403)
                    client.post(f'{schedule_base}/recalculate-actual', data={
                        'baseline_id': request.POST.get('baseline_id', ''),
                        'actual_as_of': request.POST.get('actual_as_of', ''),
                        'reason': request.POST.get('reason', ''),
                    })
                elif command == 'schedule_create':
                    if not ctx.get('can_manage_schedule'):
                        return HttpResponse('ليس لديك صلاحية إنشاء مسودة الجدولة.', status=403)
                    client.post(schedule_base, data={
                        'baseline_id': request.POST.get('baseline_id', ''),
                        'reason': request.POST.get('reason', ''),
                    })
                elif command == 'schedule_propose':
                    if not ctx.get('can_propose_schedule'):
                        return HttpResponse('ليس لديك صلاحية إرسال إصدار الجدولة للمراجعة.', status=403)
                    client.post(f'{schedule_base}/{schedule_id}/propose', data={})
                elif command == 'schedule_approve':
                    if not ctx.get('can_approve_schedule'):
                        return HttpResponse('ليس لديك صلاحية اعتماد إصدار الجدولة.', status=403)
                    client.post(f'{schedule_base}/{schedule_id}/approve', data={
                        'reason': request.POST.get('reason', ''),
                    })
                elif command == 'schedule_reject':
                    if not ctx.get('can_approve_schedule'):
                        return HttpResponse('ليس لديك صلاحية رفض إصدار الجدولة.', status=403)
                    reason = request.POST.get('reason', '').strip()
                    if not reason:
                        ctx['error'] = 'سبب الرفض مطلوب.'
                        raise ValueError('missing rejection reason')
                    client.post(f'{schedule_base}/{schedule_id}/reject', data={'reason': reason})
                else:
                    return HttpResponse('إجراء الجدولة غير متاح.', status=400)
                return redirect(f"{url(project_id, 'work-orders')}?tab=plan")
            except ValueError:
                pass
            except (ForbiddenException, NotFoundException, UnauthorizedException):
                raise
            except ApiException as exc:
                ctx['error'] = str(exc)
        if section == 'work-orders' and command.startswith('daily_'):
            if not allowed(identity, 'daily_work.manage'):
                return HttpResponse('ليس لديك صلاحية إدارة العمل اليومي', status=403)
            try:
                daily_date = request.POST.get('work_date') or date.today().isoformat()
                if command == 'daily_create':
                    client.post(f'/daily-work/projects/{project_id}/items', data={
                        'activity_id': request.POST.get('activity_id'),
                        'work_order_id': request.POST.get('work_order_id') or None,
                        'work_date': daily_date,
                        'title': request.POST.get('title') or 'عمل يومي',
                        'target_quantity': request.POST.get('target_quantity') or '0',
                        'unit': request.POST.get('unit') or '',
                        'assignee_user_id': request.POST.get('assignee_user_id') or None,
                        'team_name': request.POST.get('team_name') or '',
                        'shift': request.POST.get('shift') or '',
                        'location': request.POST.get('location') or '',
                        'notes': request.POST.get('notes') or '',
                    })
                elif command == 'daily_status':
                    client.post(f"/daily-work/projects/{project_id}/items/{request.POST['item_id']}/status", data={'status': request.POST['status']})
                elif command == 'daily_readiness':
                    client.post(f"/daily-work/projects/{project_id}/items/{request.POST['item_id']}/readiness", data={'check_type': request.POST.get('check_type') or 'general', 'result': request.POST.get('result') or 'warning', 'note': request.POST.get('note') or ''})
                elif command == 'daily_progress':
                    client.post(f"/daily-work/projects/{project_id}/items/{request.POST['item_id']}/progress", data={'quantity': request.POST['quantity'], 'notes': request.POST.get('notes') or ''})
                elif command == 'daily_blocker':
                    client.post(f"/daily-work/projects/{project_id}/items/{request.POST['item_id']}/blockers", data={'blocker_type': request.POST['blocker_type'], 'description': request.POST['description']})
                elif command == 'daily_resolve':
                    client.post(f"/daily-work/projects/{project_id}/items/{request.POST['item_id']}/blockers/{request.POST['blocker_id']}/resolve", data={'note': request.POST.get('note') or ''})
                return redirect(f"{url(project_id, 'work-orders')}?daily_date={daily_date}")
            except ApiException as exc:
                ctx['error'] = str(exc)
        ctx['failed_command'] = command
        ctx['failed_item_id'] = request.POST.get('item_id', '') if request.method=='POST' else ''
        commands = {}
        if not item:
            if section=='baselines':
                commands['approve'] = (manage_permission, None, base)
            else:
                if section != 'work-orders' or ctx.get('can_create_work_order'):
                    commands['create'] = (manage_permission,section,base)
                elif request.method == 'POST' and command == 'create':
                    return HttpResponse(ctx['execution_block_reason'], status=409)
                if manage and (section != 'work-orders' or ctx.get('can_create_work_order')):
                    initial={}
                    if section == 'work-orders' and request.method == 'GET':
                        initial['work_order_code'] = next_work_order_code(
                            project.get('project_code'), execution_orders,
                        )
                    if section=='work-orders' and request.method=='GET' and request.GET.get('activity_id'):
                        try:
                            activity_id=UUID(request.GET['activity_id']).hex
                        except ValueError:
                            return HttpResponse('مرجع النشاط غير صالح',status=400)
                        if activity_id not in {UUID(row['id']).hex for row in refs['activities']}:
                            return HttpResponse('النشاط غير متاح ضمن هذا المشروع',status=404)
                        if activity_id not in {UUID(row['id']).hex for row in form_refs['activities']}:
                            return HttpResponse('لا يمكن إصدار أمر آخر لهذا النشاط حالياً',status=409)
                        initial['activity_id']=str(UUID(request.GET['activity_id']))
                    if section=='risks' and request.method=='GET':
                        risk_rows = client.get(base)['items']
                        initial['risk_code'] = next_risk_code(project.get('project_code'), risk_rows)
                        level = request.GET.get('level', 'project')
                        level_keys = {'phase': 'phase_id', 'task': 'task_id', 'activity': 'activity_id'}
                        if level not in {'project', *level_keys}:
                            return HttpResponse('مستوى ارتباط الخطر غير صالح', status=400)
                        initial['level'] = level
                        field = level_keys.get(level)
                        if field:
                            value = request.GET.get(field, '')
                            try:
                                selected_id = UUID(value).hex
                            except ValueError:
                                return HttpResponse('العنصر المرتبط بالخطر غير صالح', status=400)
                            if selected_id not in {UUID(row['id']).hex for row in refs[{
                                'phase_id': 'phases', 'task_id': 'tasks', 'activity_id': 'activities'
                            }[field]]}:
                                return HttpResponse('العنصر غير متاح ضمن هذا المشروع', status=404)
                            # Django choice values preserve the canonical UUID
                            # string form, so use the same representation for
                            # the initial value and select the linked element.
                            initial[field] = str(UUID(value))
                    form = operation_form(section,form_refs, request.POST if command=='create' else None,
                                          initial=initial)
        elif section in CONTROL:
            if action=='edit':
                if not manage:
                    return HttpResponse('ليس لديك صلاحية التعديل',status=403)
                initial = dict(item)
                if section=='cashflows':
                    initial['currency'] = item['exchange_rate_snapshot']['from']
                form = operation_form(section,refs,request.POST if command=='save' else None,initial)
                commands['save'] = (manage_permission,section,endpoint)
            elif action=='delete':
                if not manage:
                    return HttpResponse('ليس لديك صلاحية الحذف',status=403)
                commands['delete'] = (manage_permission,None,endpoint)
            else:
                ctx['edit_url'] = url(project_id,section,entity_id)+'edit/' if manage else None
                ctx['delete_url'] = url(project_id,section,entity_id)+'delete/' if manage else None
                states = {'risks':{'active':['closed'],'closed':['active']},
                          'deviations':{'open':['closed'],'closed':['open']},
                          'reports':{'draft':['submitted'],'submitted':['approved','rejected']}}
                next_states = states.get(section,{}).get(item.get('status'),[])
                ctx['transitions'] = []
                for target in next_states:
                    perm = 'pm.projects.update' if section=='reports' and target in ('approved','rejected') else manage_permission
                    commands['status:'+target] = (perm,None,endpoint+'/status')
                    if allowed(identity,perm):
                        ctx['transitions'].append({'value':target,'label':STATUS[target]})
        elif section=='weekly-plans':
            ctx['weekly_items'] = item['items']
            activity_map = {r['id']: r for r in refs['activities']}
            weekly_user_names = {
                UUID(str(user['id'])).hex: user.get('name') or user.get('username') or 'مستخدم'
                for user in refs.get('users', []) if user.get('id')
            }
            for row in ctx['weekly_items']:
                activity = activity_map.get(row['activity_id'], {})
                row['activity_name'] = activity.get('name', 'نشاط غير متاح')
                row['activity_code'] = activity.get('activity_code', '')
                row['unit'] = activity.get('unit', '')
                row['target_display'] = row.get('weekly_target', row.get('target'))
                row['actual_display'] = row.get('actual', '0')
                row['remaining_display'] = row.get('remaining', '—')
                assignee_id = row.get('assignee_user_id')
                row['assignee_name'] = (
                    weekly_user_names.get(UUID(str(assignee_id)).hex, 'مستخدم غير متاح')
                    if assignee_id else 'غير معيّن'
                )
            ctx['weekly_baselines'] = client.get(endpoint+'/baselines')['items']
            for baseline in ctx['weekly_baselines']:
                baseline['entries'] = json.loads(baseline['snapshot'])
                for row in baseline['entries']:
                    row['activity_name'] = activity_map.get(row['activity_id'], {}).get('name', 'نشاط غير متاح')
                    assignee_id = row.get('assignee_user_id')
                    row['assignee_name'] = (
                        weekly_user_names.get(UUID(str(assignee_id)).hex, 'مستخدم غير متاح')
                        if assignee_id else 'غير معيّن'
                    )
            targets = WEP_NEXT.get(item['status'], [])
            if item.get('carried_over'):
                targets = [target for target in targets if target != 'reopened']
            for target in targets:
                commands['status:'+target] = (manage_permission, None, endpoint+'/status')
            if manage:
                ctx['transitions'] = [{'value':target, 'label':STATUS[target]} for target in targets]
            if item['status'] in ('draft', 'reopened'):
                commands['item'] = (manage_permission, 'item', endpoint+'/items')
                commands['update-item'] = (manage_permission, 'update-item', endpoint+'/items')
                if manage:
                    for row in ctx['weekly_items']:
                        row['edit_form'] = operation_form(
                            'update-item', refs,
                            request.POST if command == 'update-item' and request.POST.get('item_id') == row['id'] else None,
                            initial=row,
                        )
                        row['edit_form'].auto_id = 'pm_'+row['id']+'_%s'
            if item['status'] == 'in_progress':
                commands['close'] = (manage_permission, None, endpoint+'/close')
                ctx['can_close'] = manage
            if item['status'] == 'closed':
                ctx['closure'] = json.loads(item['closure']) if item.get('closure') else None
                if not item.get('carried_over'):
                    commands['carryover'] = (manage_permission, 'carryover', endpoint+'/carryover')
        elif section=='work-orders':
            ctx['events'] = client.get(endpoint+'/events')['items']
            for event in ctx['events']:
                if event.get('after_quantity') is None:
                    event['after_quantity'] = event.get('after')
                if event.get('after_quantity') is None and event.get('before_quantity') is not None and event.get('delta') is not None:
                    event['after_quantity'] = str(
                        decimal_value(event['before_quantity']) + decimal_value(event['delta'])
                    )
            ctx['consumptions'] = client.get(endpoint+'/consumptions')['items']
            if ctx.get('can_edit_order') and (ctx['events'] or ctx['consumptions']):
                ctx['can_edit_order'] = False
            for target in WO_NEXT.get(item['status'],[]):
                commands['status:'+target] = (manage_permission,None,endpoint+'/status')
            if item['status'] in ('issued','in_progress'):
                commands['quantity'] = (manage_permission,'quantity',endpoint+'/quantity')
            if ctx.get('can_edit_order'):
                commands['update-order'] = (manage_permission,'update-order',endpoint)
            if ctx.get('can_reject'):
                commands['reject'] = (manage_permission,'reject',endpoint+'/reject')
            if ctx.get('can_partial_close'):
                commands['partial-close'] = (manage_permission,'partial-close',endpoint+'/partial-close')
            if ctx.get('can_approve'):
                commands['approve'] = (manage_permission,None,endpoint+'/approve')
            if ctx.get('can_consume'):
                commands['consumption'] = (manage_permission,'consumption',endpoint+'/consumptions')
            if manage:
                ctx['transitions'] = [{'value':t,'label':STATUS[t]} for t in WO_NEXT.get(item['status'],[])]
        if section=='dependencies' and not item:
            commands['remove'] = (manage_permission,None,base)

        if request.method=='POST':
            if command not in commands:
                return HttpResponse('الإجراء غير متاح في الحالة الحالية',status=400)
            perm, form_kind, target_endpoint = commands[command]
            if not allowed(identity,perm):
                return HttpResponse('ليس لديك صلاحية تنفيذ الإجراء',status=403)
            submitted = form if command in ('create','save') else operation_form(form_kind,refs,request.POST) if form_kind else None
            if submitted is None or submitted.is_valid():
                data = payload(submitted) if submitted is not None else {}
                try:
                    if command.startswith('status:'):
                        data = {'status':command.split(':',1)[1]}
                        if section == 'weekly-plans':
                            data['reason'] = request.POST.get('reason', '')
                    if command=='consumption':
                        data['work_order_id'] = str(entity_id)
                    if command=='quantity':
                        data['quantity'] = str(
                            decimal_value(item.get('actual_quantity_snapshot')) + decimal_value(data['quantity'])
                        )
                    if command=='remove':
                        try:
                            dependency_id = UUID(request.POST.get('dependency_id',''))
                        except ValueError:
                            return HttpResponse('مرجع العلاقة غير صالح',status=400)
                        client.delete(base+'/'+str(dependency_id))
                    elif command=='delete':
                        client.delete(target_endpoint)
                    elif command=='update-item':
                        try:
                            commitment_id = UUID(request.POST.get('item_id',''))
                        except ValueError:
                            return HttpResponse('مرجع الالتزام غير صالح',status=400)
                        client.put(target_endpoint+'/'+str(commitment_id),data=data)
                    elif command=='update-order':
                        client.put(target_endpoint,data=data)
                    elif command=='save':
                        client.put(target_endpoint,data=data)
                    else:
                        result = client.post(target_endpoint,data=data)
                        if command=='create' and result.get('id') and section!='dependencies':
                            if section == 'weekly-plans' and request.POST.get('return_to_workspace') == '1':
                                return redirect(
                                    url(project_id, 'work-orders') +
                                    '?tab=weekly&weekly_plan_id=' + str(result['id'])
                                )
                            return redirect(url(project_id,section,result['id']))
                    if section == 'weekly-plans' and request.POST.get('return_to_workspace') == '1':
                        selected_plan_id = entity_id
                        destination = url(project_id, 'work-orders') + '?tab=weekly'
                        if selected_plan_id:
                            destination += '&weekly_plan_id=' + str(selected_plan_id)
                        return redirect(destination)
                    return redirect(url(project_id,section,None if command=='delete' else entity_id))
                except (ForbiddenException,NotFoundException,UnauthorizedException):
                    raise
                except ApiException:
                    ctx['error'] = 'لم يُحفظ الإجراء. تحقق من تفرد الرمز والتواريخ وسعر الصرف وحالة العنصر. الاعتماد يتطلب التزامات صالحة، وإعادة الفتح تتطلب سببًا، ولا يقبل ترابط الأنشطة الدورات.'
            else:
                ctx['error'] = 'صحح الحقول المشار إليها ثم أعد المحاولة.'
        ctx['form'] = form
        ctx['form_sections'] = group_form_fields(form, section) if form is not None else []
        ctx['command'] = 'save' if action=='edit' else 'create'
        ctx['command_forms'] = []
        for key, title in [('update-order','تعديل بيانات الأمر'),('quantity','تسجيل دفعة إنجاز'),
                           ('consumption','إضافة استهلاك فعلي'),('partial-close','إغلاق جزئي مع السبب'),
                           ('reject','رفض أمر التشغيل مع السبب'),('item','إضافة التزام أسبوعي'),
                           ('carryover','ترحيل المتبقي إلى أسبوع لاحق')]:
            if key in commands and manage:
                if key == 'quantity':
                    initial = {'quantity': '0'}
                elif key == 'consumption':
                    initial = {'consumption_code': next_consumption_code(
                        item['work_order_code'], ctx['consumptions'])}
                else:
                    initial = item if key == 'update-order' else None
                command_form = operation_form(
                    commands[key][1],
                    form_refs,
                    request.POST if command == key else None,
                    initial=initial,
                )
                command_form.auto_id = 'pm_'+key+'_%s'
                if command==key and request.method=='POST':
                    command_form.is_valid()
                ctx['command_forms'].append({'command':key,'title':title,
                    'form':command_form,
                    'form_sections':group_form_fields(command_form,commands[key][1])})
        if item:
            ctx['status_label'] = STATUS.get(item.get('status'),item.get('status',''))
            if section in CONTROL or section=='work-orders':
                display = operation_form(section,refs,initial=item)
                details = []
                for key, field in display.fields.items():
                    value = item.get(key,'')
                    if section=='cashflows' and key=='currency':
                        value=item['exchange_rate_snapshot']['from']
                    if isinstance(field, forms.ChoiceField):
                        value = dict(field.choices).get(value,value)
                    details.append({'label':field.label,'value':value})
                ctx['details'] = details
            if section=='baselines':
                ctx['baseline'] = item['baseline']
                ctx['baseline_items'] = item['items']
                for row in ctx['baseline_items']:
                    row['facts'] = json.loads(row['snapshot'])
        else:
            rows = execution_orders if section == 'work-orders' else (
                risk_rows if section == 'risks' and risk_rows is not None else client.get(base)['items']
            )
            names = {r['id']:r['name'] for r in refs['activities']}
            for row in rows:
                if section != 'work-orders':
                    row['href'] = url(project_id,section,row['id']) if section!='dependencies' else None
                row['display'] = row.get('name') or row.get('week_code') or str(row.get('version',''))
                row['status_label'] = STATUS.get(row.get('status'), row.get('status', ''))
                if section == 'work-orders':
                    row['display'] = row.get('work_order_code', '')
                if section=='dependencies':
                    row['predecessor'] = names.get(row['predecessor_id'],'نشاط غير متاح')
                    row['successor'] = names.get(row['successor_id'],'نشاط غير متاح')
                    row['type_label'] = dict(operation_form('dependencies',refs).fields['dependency_type'].choices)[row['dependency_type']]
            if section == 'risks':
                level_labels = {'project': 'المشروع', 'phase': 'المرحلة', 'task': 'المهمة', 'activity': 'النشاط'}
                linked_names = {
                    'phase': {str(value['id']): value.get('name', '') for value in refs.get('phases', [])},
                    'task': {str(value['id']): value.get('name', '') for value in refs.get('tasks', [])},
                    'activity': {str(value['id']): value.get('name', '') for value in refs.get('activities', [])},
                }
                for row in rows:
                    risk_level = row.get('level') or 'project'
                    row['level_label'] = level_labels.get(risk_level, risk_level)
                    link_field = {'phase': 'phase_id', 'task': 'task_id', 'activity': 'activity_id'}.get(risk_level)
                    row['linked_name'] = (
                        linked_names.get(risk_level, {}).get(str(row.get(link_field)), 'ارتباط غير محدد')
                        if link_field else 'نطاق المشروع'
                    )
                    row['importance'] = decimal_value(row.get('importance'))
                    row['severity_value'] = row['importance']
                    row['severity_class'] = (
                        'high' if row['severity_value'] >= Decimal('12')
                        else 'medium' if row['severity_value'] >= Decimal('5')
                        else 'low'
                    )
            ctx['rows'] = rows
            if section=='cashflows':ctx['cash_summary']=cash_summary(rows)
            if section=='communications':
                user_names = {str(user['id']): user.get('name', '') for user in refs.get('users', [])}
                for row in rows:
                    row['sender_name'] = user_names.get(str(row.get('sender_user_id') or ''), '')
                ctx['communication_summary'] = {
                    'with_report_type': sum(bool(row.get('report_type')) for row in rows),
                    'with_sender': sum(bool(row.get('sender_user_id')) for row in rows),
                    'with_mechanism': sum(bool(row.get('mechanism')) for row in rows),
                }
            ctx['state_counts']=[{'label':STATUS[state],'count':sum(r.get('status')==state for r in rows)}
                for state in ('draft','active','open','issued','submitted','review','approved','in_progress','completed','closed','rejected')
                if any(r.get('status')==state for r in rows)]
        if section == 'work-orders' and item and request.GET.get('print') == '1':
            project_risks = (
                client.get(f'/pm/projects/{project_id}/risks')['items']
                if ctx.get('can_view_risks') else []
            )
            print_doc = prepare_work_order_print_document(
                item, refs, project, ctx.get('events', []), ctx.get('consumptions', []),
                project_risks, ctx.get('can_view_risks', False),
            )
            ctx.update(print_doc)
            ctx['print_orders'] = [print_doc]
            ctx['bulk_print'] = False
            return render(request, 'pm/work_order_print.html', ctx)

        if (
            section == 'work-orders' and not item
            and request.GET.get('bulk_print') == '1'
        ):
            requested_ids = request.GET.getlist('order_id')
            if not requested_ids or len(requested_ids) > 50:
                return HttpResponse('حدد من أمر واحد إلى 50 أمر تشغيل للطباعة.', status=400)
            try:
                requested_ids = list(dict.fromkeys(UUID(value).hex for value in requested_ids))
            except (TypeError, ValueError):
                return HttpResponse('تتضمن قائمة الطباعة معرف أمر غير صالح.', status=400)
            visible_orders = {
                UUID(str(order['id'])).hex: order for order in execution_orders
            }
            if any(order_id not in visible_orders for order_id in requested_ids):
                return HttpResponse('أحد أوامر التشغيل المحددة غير متاح ضمن نطاق المشروع.', status=404)
            project_risks = (
                client.get(f'/pm/projects/{project_id}/risks')['items']
                if ctx.get('can_view_risks') else []
            )
            print_docs = []
            for order_id in requested_ids:
                order_endpoint = f'{base}/{order_id}'
                order_item = client.get(order_endpoint)
                events = client.get(order_endpoint + '/events')['items']
                consumptions = client.get(order_endpoint + '/consumptions')['items']
                print_docs.append(prepare_work_order_print_document(
                    order_item, refs, project, events, consumptions,
                    project_risks, ctx.get('can_view_risks', False),
                ))
            ctx.update({
                **print_docs[0],
                'print_orders': print_docs,
                'bulk_print': True,
            })
            return render(request, 'pm/work_order_print.html', ctx)

        template = 'pm/execution_workspace.html' if section == 'work-orders' else 'pm/operations.html'
        return render(request, template, ctx, status=400 if ctx.get('error') else 200)
    except UnauthorizedException:
        return redirect('auth:login')
    except ForbiddenException:
        return HttpResponse('ليس لديك صلاحية لهذا المشروع أو الإجراء',status=403)
    except NotFoundException:
        return HttpResponse('العنصر غير متاح ضمن نطاقك',status=404)
    except ApiException:
        return HttpResponse('تعذر الاتصال بالخدمة؛ حاول مجددًا',status=503)
