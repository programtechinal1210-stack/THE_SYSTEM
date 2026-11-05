import json
from uuid import UUID
from datetime import date
from django.http import HttpResponse
from decimal import Decimal, InvalidOperation
from django.shortcuts import render,redirect
from django.views.decorators.http import require_GET
from shared.services.api_client import ApiClient,ApiException,ForbiddenException,NotFoundException,UnauthorizedException,ValidationException


REPORTS={'executive':'التقرير الشامل للمشروع','hierarchy':'التسلسل الهرمي','schedule':'المدد والاعتماديات','risk':'المخاطر','resources':'الموارد',
         'work-orders':'أوامر التشغيل','exceptions':'الاستثناءات','execution':'تقرير التنفيذ والإنجاز',
         'weekly-plans':'تقرير الخطط الأسبوعية'}
LABELS={'phase_code':'المرحلة','task_code':'المهمة','activity_code':'النشاط','name':'الاسم',
        'planned_quantity':'الكمية المخططة','actual_quantity':'الكمية الفعلية','unit':'الوحدة','planned_duration':'المدة المخططة',
        'predecessors':'الأنشطة السابقة','requirement_code':'الاحتياج','quantity':'الكمية','planned_cost':'التكلفة المخططة',
        'actual_cost':'التكلفة الفعلية','currency':'العملة','risk_code':'المخاطرة','status':'الحالة','probability':'الاحتمال',
        'impact':'الأثر','importance':'الأهمية','corrective_action':'الإجراء التصحيحي','work_order_code':'أمر التشغيل',
        'code':'الرمز','exception':'الاستثناء'}


@require_GET
def report_center(request):
    client=ApiClient(token=request.session.get('access_token'))
    try:
        data=client.get('/pm/reporting/portfolio')
        request.core_identity=client.get('/auth/me')
        request.core_modules=client.get('/modules')
        items=data.get('items',[])
        project_id=str(UUID(items[0]["project_id"])) if items else ''
        project_href=f'/pm/projects/{project_id}' if project_id else ''
        return render(request,'pm/report_center.html',{'page_title':'مركز التقارير','items':items,'project_href':project_href,'project_id':project_id})
    except UnauthorizedException:
        return redirect('auth:login')
    except ForbiddenException:
        return HttpResponse('ليس لديك صلاحية تقارير المشاريع',status=403)
    except ApiException:
        return HttpResponse('تعذر تحميل التقارير',status=503)


@require_GET
def portfolio(request):
    client=ApiClient(token=request.session.get('access_token'))
    try:
        data=client.get('/pm/reporting/portfolio',params={'status':request.GET['status']} if request.GET.get('status') else {})
        request.core_identity=client.get('/auth/me')
        request.core_modules=client.get('/modules')
        items=data.get('items',[])
        status_labels={'planning':'قيد التخطيط','in_progress':'قيد التنفيذ','completed':'مكتمل','closed':'مغلق',
                       'draft':'مسودة','pending_approval':'بانتظار الإقرار','ready':'بانتظار البدء'}
        for row in items:
            row['href']=f'/pm/projects/{UUID(row["project_id"])}/reporting/'
            row['status_label']=status_labels.get(row.get('status'),row.get('status') or 'غير محدد')
            row['intervention']=bool(row.get('open_risks') or row.get('open_deviations'))
            reasons=[]
            if row.get('open_risks'): reasons.append(f'{row["open_risks"]} مخاطر مفتوحة')
            if row.get('open_deviations'): reasons.append(f'{row["open_deviations"]} انحرافات مفتوحة')
            row['intervention_reason']=' و'.join(reasons) if reasons else ''
        status_counts=[]
        for code,label in status_labels.items():
            count=sum(1 for row in items if row.get('status')==code)
            if count: status_counts.append({'code':code,'label':label,'count':count})
        currencies={row.get('currency') for row in items if row.get('currency')}
        cost_by_currency=[]
        for currency in sorted(currencies):
            planned=sum((Decimal(str(row.get('planned_cost') or 0)) for row in items if row.get('currency')==currency),Decimal('0'))
            actual=sum((Decimal(str(row.get('actual_cost') or 0)) for row in items if row.get('currency')==currency),Decimal('0'))
            cost_by_currency.append({'currency':currency,'planned':planned,'actual':actual})
        context={'page_title':'تقرير محفظة المشاريع','items':items,'status_labels':status_labels,
                 'status_counts':status_counts,'cost_by_currency':cost_by_currency,
                 'summary':{'total':len(items),'in_progress':sum(row.get('status')=='in_progress' for row in items),
                            'completed':sum(row.get('status') in ('completed','closed') for row in items),
                            'delayed':None,'intervention':sum(row['intervention'] for row in items)},
                 'filter_status':request.GET.get('status',''),'filter_query':request.GET.urlencode(),
                 'data_note':'التصنيف المتأخر يحتاج إلى خط أساس زمني معتمد غير متاح في مصدر المحفظة الحالي.'}
        return render(request,'pm/portfolio.html',context)
    except UnauthorizedException:
        return redirect('auth:login')
    except ForbiddenException:
        return HttpResponse('ليس لديك صلاحية تقارير المشاريع',status=403)
    except ApiException:
        return HttpResponse('تعذر تحميل التقارير',status=503)


@require_GET
def reporting(request,project_id):
    client=ApiClient(token=request.session.get('access_token'))
    params={key:value for key,value in request.GET.items() if key in ('date_from','date_to','phase_id','task_id','activity_id','status') and value}
    risk_params={key:value for key,value in request.GET.items() if key in ('risk_status','severity','q') and value}
    root=f'/pm/projects/{project_id}'
    try:
        if request.GET.get('download')=='json' and request.GET.get('report') != 'productivity':
            export_params={**params,**risk_params} if request.GET.get('report')=='risk' else params
            data=client.get(root+'/reporting/export',params=export_params)
            result=HttpResponse(json.dumps(data,ensure_ascii=False,indent=2),content_type='application/json; charset=utf-8')
            result['Content-Disposition']='attachment; filename="project-report.json"'
            return result
        center=client.get(root+'/command-center',params=params)
        costs=client.get(root+'/reporting/cost',params=params)['items']
        progress=client.get(root+'/reporting/progress',params=params)['items']
        options=client.get(root+'/reporting/options')
        kind=request.GET.get('report','executive')
        REPORTS.setdefault('productivity', 'تقرير الأداء والإنتاجية')
        if kind not in REPORTS and kind != 'costs':return HttpResponse(status=404)
        if kind == 'resources':
            planned = client.get(root + '/reporting/resources', params=params)
            actual_orders = client.get(root + '/reporting/work-orders', params=params)
            requirements = planned.get('items', [])
            order_rows = actual_orders.get('items', [])
            planned_cost = sum((Decimal(str(row.get('planned_cost') or 0)) for row in requirements), Decimal('0'))
            actual_cost = sum((Decimal(str(row.get('actual_cost') or 0)) for row in order_rows), Decimal('0'))
            rows = [{'code': row.get('requirement_code') or '—', 'name': row.get('name') or '—',
                     'activity': row.get('activity_code') or '—', 'quantity': row.get('quantity') or '—',
                     'unit': row.get('unit') or '—', 'planned_cost': row.get('planned_cost') or '—',
                     'currency': row.get('currency') or center.get('currency') or '',
                     'kind': 'unknown'} for row in requirements]
            context = {'page_title':'تقرير الموارد', 'center':center, 'options':options,
                'filters':params, 'export_query':request.GET.urlencode(), 'resource_rows':rows,
                'planned_count':len({row.get('code') for row in rows if row.get('code') and row.get('code') != '—'}),
                'actual_count':None, 'attention_count':None, 'planned_cost':planned_cost,
                'actual_cost':actual_cost, 'currency':center.get('currency') or '',
                'actual_order_count':len(order_rows),
                'resource_data_note':'المتاح حالياً هو احتياجات PM المخططة واستهلاك أوامر التشغيل إجمالياً. لا يميز عقد المصدر نوع المورد ولا يربط الاستهلاك التفصيلي باحتياج محدد؛ لذلك تعرض تبويبات المواد والمعدات والعمالة كغير متاحة ولا يُستنتج عدد موارد مستخدمة أو موارد تحتاج متابعة.'}
            request.core_identity=client.get('/auth/me')
            request.core_modules=client.get('/modules')
            return render(request, 'pm/resources_report.html', context)
        if kind == 'costs':
            schedule = client.get(root+'/reporting/schedule', params=params).get('items', [])
            phase_labels = [row.get('name') for row in options.get('phases', [])]
            activity_map = {row.get('activity_code'): row for row in schedule}
            rows = []
            zero = Decimal('0')
            for item in costs:
                planned = Decimal(str(item.get('planned_cost') or 0))
                actual = Decimal(str(item.get('actual_cost') or 0))
                activity = activity_map.get(item.get('activity_code'), {})
                phase_code = activity.get('phase_code')
                phase_label = next((label for label in phase_labels if str(label).startswith(str(phase_code))), None)
                rows.append({'activity_code': item.get('activity_code') or '—',
                    'activity_name': activity.get('name') or item.get('activity_code') or '—',
                    'phase_code': phase_code or '—', 'phase_name': phase_label or phase_code or '—',
                    'planned': planned, 'actual': actual, 'variance': planned - actual,
                    'ratio': (actual / planned * 100) if planned else None, 'over_plan': actual > planned})
            phase_totals = {}
            for row in rows:
                bucket = phase_totals.setdefault(row['phase_code'], {'phase_code': row['phase_code'],
                    'phase_name': row['phase_name'], 'planned': zero, 'actual': zero})
                bucket['planned'] += row['planned']
                bucket['actual'] += row['actual']
            phase_rows = sorted(phase_totals.values(), key=lambda row: row['phase_name'])
            phase_scale = max((max(row['planned'], row['actual']) for row in phase_rows), default=zero)
            for row in phase_rows:
                row['variance'] = row['planned'] - row['actual']
                row['planned_width'] = float(row['planned'] / phase_scale * 100) if phase_scale else 0
                row['actual_width'] = float(row['actual'] / phase_scale * 100) if phase_scale else 0
            planned_total = sum((row['planned'] for row in rows), zero)
            actual_total = sum((row['actual'] for row in rows), zero)
            currency = center.get('currency') or ''
            context = {'page_title': 'التقرير المالي والتكاليف', 'center': center,
                'options': options, 'filters': params, 'export_query': request.GET.urlencode(),
                'cost_rows': rows, 'phase_rows': phase_rows, 'currency': currency,
                'planned_total': planned_total, 'actual_total': actual_total,
                'variance_total': planned_total - actual_total,
                'spend_ratio': (actual_total / planned_total * 100) if planned_total else None,
                'review_rows': [row for row in rows if row['over_plan']],
                'period_basis': center.get('period_basis')}
            request.core_identity=client.get('/auth/me')
            request.core_modules=client.get('/modules')
            return render(request, 'pm/costs_report.html', context)
        if kind == 'executive':
            bundle = client.get(root+'/reporting/export',params=params)
            schedule = bundle.get('schedule', {}).get('items', [])
            risks = bundle.get('risk', {}).get('items', [])
            work_orders = bundle.get('work-orders', {}).get('items', [])
            exceptions = bundle.get('exceptions', {}).get('items', [])
            resources = bundle.get('resources', {}).get('items', [])
            planned_hours = sum((Decimal(str(item.get('planned_duration') or 0)) for item in schedule), Decimal('0'))
            status_labels = {
                'draft': 'مسودة', 'planning': 'قيد التخطيط', 'pending_approval': 'بانتظار الإقرار',
                'approved': 'معتمد', 'ready': 'بانتظار بدء التنفيذ', 'in_progress': 'قيد التنفيذ',
                'completed': 'مكتمل', 'closed': 'مغلق',
            }
            lifecycle_index = {
                'draft': 1, 'planning': 2, 'pending_approval': 3, 'approved': 4,
                'ready': 4, 'in_progress': 5, 'completed': 6, 'closed': 8,
            }.get(center.get('status'), 0)
            try:
                progress_percent = (Decimal(str(center.get('progress'))) * Decimal('100')).quantize(Decimal('0.01')) if center.get('progress') is not None else None
            except (InvalidOperation, TypeError, ValueError):
                progress_percent = None
            context = {
                'page_title': 'التقرير الشامل للمشروع',
                'center': center,
                'options': options,
                'filters': params,
                'export_query': request.GET.urlencode(),
                'reports': REPORTS.items(),
                'report_kind': kind,
                'summary': {
                    'progress': center.get('progress'),
                    'progress_percent': progress_percent,
                    'planned_cost': center.get('planned_cost'),
                    'actual_cost': center.get('actual_cost'),
                    'planned_hours': planned_hours,
                    'activities': len(options.get('activities', [])),
                },
                'status_label': status_labels.get(center.get('status'), center.get('status') or 'غير محدد'),
                'lifecycle_index': lifecycle_index,
                'schedule': schedule,
                'risks': risks,
                'work_orders': work_orders,
                'exceptions': exceptions,
                'resources': resources,
                'progress_rows': bundle.get('progress', []),
                'cost_rows': bundle.get('cost', []),
                'currency': bundle.get('command_center', {}).get('currency') or center.get('currency'),
                'period_basis': center.get('period_basis'),
                'data_available': {
                    'schedule': bool(schedule), 'risks': bool(risks), 'work_orders': bool(work_orders),
                    'exceptions': bool(exceptions), 'resources': bool(resources),
                },
            }
            request.core_identity=client.get('/auth/me')
            request.core_modules=client.get('/modules')
            return render(request, 'pm/comprehensive_report.html', context)
        if kind == 'weekly-plans':
            plans = client.get(root + '/weekly-plans').get('items', [])

            def decimal_value(value):
                try:
                    return Decimal(str(value if value is not None else '0'))
                except (InvalidOperation, TypeError, ValueError):
                    return Decimal('0')

            def display_number(value):
                amount = decimal_value(value)
                return format(amount.normalize(), 'f') if amount else '0'

            plan_status_labels = {
                'draft': 'مسودة', 'review': 'قيد المراجعة', 'approved': 'معتمدة',
                'in_progress': 'قيد التنفيذ', 'closed': 'مغلقة', 'reopened': 'معاد فتحها',
            }
            selected_week = request.GET.get('week', '')
            selected_status = request.GET.get('status', '')
            if selected_week:
                plans = [plan for plan in plans if plan.get('id') == selected_week]
            if selected_status:
                plans = [plan for plan in plans if plan.get('status') == selected_status]
            if request.GET.get('date_from'):
                plans = [plan for plan in plans if str(plan.get('end_date') or '') >= request.GET['date_from']]
            if request.GET.get('date_to'):
                plans = [plan for plan in plans if str(plan.get('start_date') or '') <= request.GET['date_to']]

            activities = {str(row.get('id')): row for row in options.get('activities', [])}
            plan_rows = []
            exception_rows = []
            for plan in plans:
                detail = client.get(root + '/weekly-plans/' + str(plan['id']))
                frozen = bool(detail.get('frozen'))
                closed = detail.get('status') == 'closed' and frozen
                raw_items = detail.get('items', [])
                target_total = Decimal('0')
                actual_total = Decimal('0')
                fulfilled = 0
                unfulfilled = 0
                item_rows = []
                for item in raw_items:
                    target = decimal_value(item.get('target', item.get('weekly_target')))
                    actual = decimal_value(item.get('actual'))
                    target_total += target
                    actual_total += actual
                    commitment_met = item.get('commitment_met') if closed else None
                    if commitment_met is True:
                        fulfilled += 1
                    elif commitment_met is False:
                        unfulfilled += 1
                    activity = activities.get(str(item.get('activity_id')), {})
                    row = {
                        'activity_id': str(item.get('activity_id') or ''),
                        'activity_name': activity.get('name') or item.get('activity_name') or 'نشاط غير متاح',
                        'activity_code': activity.get('activity_code') or activity.get('code') or '—',
                        'target': display_number(target), 'actual': display_number(actual),
                        'remaining': display_number(max(target - actual, Decimal('0'))),
                        'unit': activity.get('unit') or '—',
                        'commitment_met': commitment_met,
                        'undated_actual': bool(item.get('undated_actual')),
                    }
                    item_rows.append(row)
                    if closed and commitment_met is False:
                        exception_rows.append({
                            **row, 'week_code': detail.get('week_code') or plan.get('week_code') or '—',
                            'plan_status': 'مُرحّل' if detail.get('carried_over') else 'غير محقق',
                            'carryover': bool(detail.get('carried_over')),
                        })
                closure = detail.get('closure') or {}
                if isinstance(closure, str):
                    try:
                        closure = json.loads(closure)
                    except json.JSONDecodeError:
                        closure = {}
                ppc = decimal_value(closure.get('ppc')) if closed else None
                plan_rows.append({
                    'id': str(plan['id']), 'week_code': detail.get('week_code') or plan.get('week_code') or '—',
                    'start_date': detail.get('start_date') or plan.get('start_date') or '—',
                    'end_date': detail.get('end_date') or plan.get('end_date') or '—',
                    'status': detail.get('status') or plan.get('status') or 'draft',
                    'status_label': plan_status_labels.get(detail.get('status') or plan.get('status'), 'غير محددة'),
                    'items_count': len(item_rows), 'target_total': display_number(target_total),
                    'actual_total': display_number(actual_total), 'fulfilled': fulfilled,
                    'unfulfilled': unfulfilled, 'ppc': display_number(ppc) if ppc is not None else None,
                    'ppc_bar': min(float(ppc or 0), 100), 'closed': closed,
                    'carried_over': bool(detail.get('carried_over')), 'items': item_rows,
                })

            max_quantity = max((max(decimal_value(row['target_total']), decimal_value(row['actual_total'])) for row in plan_rows), default=Decimal('0'))
            for row in plan_rows:
                row['target_bar'] = float(decimal_value(row['target_total']) * 100 / max_quantity) if max_quantity else 0
                row['actual_bar'] = float(decimal_value(row['actual_total']) * 100 / max_quantity) if max_quantity else 0
            closed_rows = [row for row in plan_rows if row['closed']]
            total_commitments = sum(row['items_count'] for row in plan_rows)
            total_fulfilled = sum(row['fulfilled'] for row in closed_rows)
            total_unfulfilled = sum(row['unfulfilled'] for row in closed_rows)
            completed_targets = sum((decimal_value(row['target_total']) for row in closed_rows), Decimal('0'))
            ppc = (Decimal(total_fulfilled) * 100 / sum((row['items_count'] for row in closed_rows), 0)
                   if closed_rows and sum((row['items_count'] for row in closed_rows), 0) else None)
            context = {
                'page_title': 'تقرير الخطط الأسبوعية', 'center': center, 'options': options,
                'filters': params, 'export_query': request.GET.urlencode(), 'plan_rows': plan_rows,
                'exception_rows': exception_rows, 'week_choices': client.get(root + '/weekly-plans').get('items', []),
                'week_filter': selected_week, 'status_filter': selected_status,
                'summary': {
                    'plans': len(plan_rows), 'commitments': total_commitments, 'fulfilled': total_fulfilled,
                    'unfulfilled': total_unfulfilled,
                    'unjudged': max(total_commitments - total_fulfilled - total_unfulfilled, 0),
                    'ppc': display_number(ppc) if ppc is not None else '—',
                    'ppc_bar': min(float(ppc or 0), 100), 'closed_plans': len(closed_rows),
                    'completed_targets': display_number(completed_targets),
                },
                'data_note': 'PPC والالتزام المحقق يُحسبان فقط من لقطة إغلاق الأسبوع المعتمدة. الخطط المفتوحة تعرض الالتزام والفعلي المؤرخ دون حكم تحقق نهائي؛ ولا يتوفر في العقد سبب للتأخير.',
            }
            request.core_identity=client.get('/auth/me')
            request.core_modules=client.get('/modules')
            return render(request, 'pm/weekly_plans_report.html', context)
        if kind == 'risk':
            extra=client.get(root+'/reporting/risk',params={**params,**risk_params})
            cost_exceptions=client.get(root+'/reporting/exceptions',params=params).get('items',[])
            risk_rows=extra.get('items',[])
            action_rows=[row for row in risk_rows if row.get('status')=='active' and row.get('corrective_action')]
            active_count=sum(row.get('status')=='active' for row in risk_rows)
            severity_counts={
                'high':sum(Decimal(str(row.get('importance') or 0))>=Decimal('12') for row in risk_rows),
                'medium':sum(Decimal('5')<=Decimal(str(row.get('importance') or 0))<Decimal('12') for row in risk_rows),
                'low':sum(Decimal(str(row.get('importance') or 0))<Decimal('5') for row in risk_rows),
            }
            for row in risk_rows:
                value=Decimal(str(row.get('importance') or 0))
                row['severity_key']='high' if value>=12 else 'medium' if value>=5 else 'low'
                row['severity_label']={'high':'مرتفعة','medium':'متوسطة','low':'منخفضة'}[row['severity_key']]
                row['status_label']='نشط' if row.get('status')=='active' else 'مغلق' if row.get('status')=='closed' else row.get('status') or 'غير محدد'
                row['linked_item']=' / '.join(value for value in (row.get('phase_code'),row.get('task_code'),row.get('activity_code')) if value) or 'المشروع'
                row['record_date']=str(row.get('discovery_date') or row.get('created_at') or '')[:10] or '—'
            maximum=max(severity_counts.values(),default=0)
            severity_rows=[{'key':key,'label':label,'count':severity_counts[key],
                            'width':round(severity_counts[key]*100/maximum) if maximum else 0}
                           for key,label in (('high','مرتفعة'),('medium','متوسطة'),('low','منخفضة'))]
            project_list=client.get('/pm/reporting/portfolio').get('items',[])
            for project in project_list:
                project['project_id']=str(UUID(project['project_id']))
            request.core_identity=client.get('/auth/me')
            request.core_modules=client.get('/modules')
            return render(request,'pm/risks_deviations_report.html',{
                'page_title':'تقرير المخاطر والانحرافات','center':center,'options':options,
                'projects':project_list,'risk_rows':risk_rows,'exception_rows':cost_exceptions,
                'action_rows':action_rows,'active_count':active_count,
                'exception_count':len(cost_exceptions),'severity_rows':severity_rows,
                'period':{'from':params.get('date_from',''),'to':params.get('date_to','')},
                'filters':{**params,**risk_params},'risk_params':risk_params,
                'filter_query':request.GET.urlencode(),
                'selected_project_id':str(project_id),
                'data_note':extra.get('note') or '',
                'exceptions_note':'يعرض هذا القسم تجاوزات التكلفة المحسوبة من مقارنة التكلفة الفعلية بالمخططة. لا يملك العقد الحالي سجلاً موحداً للانحرافات المسجلة أو قيمها المخططة والفعلية وأسبابها.',
                'severity_note':'تصنيف العرض يستخدم حدود مؤشر الأهمية الحالية: مرتفعة ≥ 12، متوسطة ≥ 5، منخفضة < 5. لا توجد عتبة معتمدة لفئة حرجة؛ لذلك لا يُشتق عدد المخاطر الحرجة.',
                'intervention_note':'لا توجد قاعدة معتمدة لتحديد الحالات التي تتطلب تدخلاً عاجلاً. تعرض الإجراءات المسجلة على المخاطر النشطة للمتابعة دون احتسابها كمؤشر تدخل.',
            })
        if kind == 'work-orders':
            schedule = client.get(root+'/reporting/schedule', params=params).get('items', [])
            work_orders = client.get(root+'/reporting/work-orders', params=params).get('items', [])

            def decimal_or_none(value):
                try:
                    return Decimal(str(value))
                except (InvalidOperation, TypeError, ValueError):
                    return None

            def percentage(actual, planned):
                actual_value = decimal_or_none(actual)
                planned_value = decimal_or_none(planned)
                if actual_value is None or planned_value in (None, Decimal('0')):
                    return None
                return (actual_value * Decimal('100') / planned_value).quantize(Decimal('0.01'))

            schedule_by_activity = {row.get('activity_code'): row for row in schedule}
            orders_by_activity = {}
            for row in work_orders:
                orders_by_activity.setdefault(row.get('activity_code'), []).append(row)
            status_labels = {
                'issued': 'صادر', 'in_progress': 'قيد التنفيذ', 'completed': 'مكتمل',
                'closed': 'مغلق', 'rejected': 'مرفوض',
            }
            order_rows = []
            for row in work_orders:
                activity_code = row.get('activity_code')
                activity = schedule_by_activity.get(activity_code, {})
                only_order_for_activity = len(orders_by_activity.get(activity_code, [])) == 1
                planned = activity.get('planned_quantity') if only_order_for_activity else None
                actual = row.get('actual_quantity')
                planned_decimal = decimal_or_none(planned)
                actual_decimal = decimal_or_none(actual)
                remaining = max(planned_decimal - actual_decimal, Decimal('0')) if planned_decimal is not None and actual_decimal is not None else None
                order_rows.append({
                    'code': row.get('work_order_code') or '—', 'activity_code': activity_code or '—',
                    'activity_name': activity.get('name') or 'غير متاح',
                    'phase_code': activity.get('phase_code') or 'غير متاح',
                    'task_code': activity.get('task_code') or 'غير متاح',
                    'status': row.get('status') or 'unknown',
                    'status_label': status_labels.get(row.get('status'), row.get('status') or 'غير متاح'),
                    'planned_quantity': planned, 'actual_quantity': actual,
                    'remaining_quantity': str(remaining) if remaining is not None else None,
                    'unit': activity.get('unit') or 'غير متاح',
                    'achievement_percent': percentage(actual, planned),
                    'actual_cost': row.get('actual_cost'), 'currency': row.get('currency') or center.get('currency'),
                    'has_unique_activity_order': only_order_for_activity,
                })
            status_counts = {status: sum(row.get('status') == status for row in work_orders) for status in status_labels}
            context = {
                'page_title': 'تقرير أوامر التشغيل', 'center': center, 'options': options,
                'filters': params, 'export_query': request.GET.urlencode(), 'order_rows': order_rows,
                'work_order_status': params.get('status', ''), 'status_counts': status_counts,
                'summary': {'total': len(work_orders), 'completed': status_counts['completed'] + status_counts['closed'],
                            'in_progress': status_counts['in_progress'], 'follow_up': status_counts['issued']},
                'data_note': 'الكمية المخططة ونسبة الإنجاز على مستوى أمر التشغيل تظهران فقط عندما يكون للأمر نشاط واحد غير مكرر ضمن النطاق. لا يوفّر عقد التقرير الحالي المسؤول أو تواريخ الإصدار والإنجاز.',
                'period_basis': center.get('period_basis'),
            }
            request.core_identity=client.get('/auth/me')
            request.core_modules=client.get('/modules')
            return render(request, 'pm/work_orders_report.html', context)
        if kind == 'execution':
            schedule = client.get(root+'/reporting/schedule', params=params).get('items', [])
            work_orders = client.get(root+'/reporting/work-orders', params=params).get('items', [])
            risks = client.get(root+'/reporting/risk', params=params).get('items', [])
            exceptions = client.get(root+'/reporting/exceptions', params=params).get('items', [])

            def decimal_or_none(value):
                try:
                    return Decimal(str(value))
                except (InvalidOperation, TypeError, ValueError):
                    return None

            def percentage(value):
                amount = decimal_or_none(value)
                if amount is None:
                    return None
                return (amount * Decimal('100')).quantize(Decimal('0.01'))

            progress_by_activity = {row.get('activity_code'): row for row in progress}
            work_orders_by_activity = {}
            for work_order in work_orders:
                work_orders_by_activity.setdefault(work_order.get('activity_code'), []).append(work_order)

            phase_names = {str(row.get('name', '')).split(' — ', 1)[0]: row.get('name') for row in options.get('phases', [])}
            phase_rows = {}
            activity_rows = []
            status_labels = {
                'completed': 'مكتمل', 'in_progress': 'قيد التنفيذ', 'not_started': 'لم يبدأ',
                'unavailable': 'غير متاح',
            }
            for scheduled in schedule:
                activity_code = scheduled.get('activity_code')
                measured = progress_by_activity.get(activity_code, {})
                planned = decimal_or_none(measured.get('planned_quantity'))
                actual = decimal_or_none(measured.get('actual_quantity'))
                achievement = decimal_or_none(measured.get('achievement'))
                if achievement is None:
                    activity_status = 'unavailable'
                elif achievement >= Decimal('1'):
                    activity_status = 'completed'
                elif achievement > Decimal('0'):
                    activity_status = 'in_progress'
                else:
                    activity_status = 'not_started'
                remaining = max(planned - actual, Decimal('0')) if planned is not None and actual is not None else None
                related_orders = work_orders_by_activity.get(activity_code, [])
                phase_code = scheduled.get('phase_code') or '—'
                phase = phase_rows.setdefault(phase_code, {
                    'code': phase_code,
                    'name': phase_names.get(phase_code) or phase_code,
                    'activities': 0,
                    'completed': 0,
                    'in_progress': 0,
                    'work_orders': 0,
                })
                phase['activities'] += 1
                phase['completed'] += activity_status == 'completed'
                phase['in_progress'] += activity_status == 'in_progress'
                phase['work_orders'] += len(related_orders)
                activity_rows.append({
                    'code': activity_code or '—', 'name': scheduled.get('name') or '—',
                    'phase_code': phase_code, 'task_code': scheduled.get('task_code') or '—',
                    'planned_quantity': measured.get('planned_quantity'), 'actual_quantity': measured.get('actual_quantity'),
                    'remaining_quantity': str(remaining) if remaining is not None else None,
                    'unit': measured.get('unit') or scheduled.get('unit') or '—',
                    'achievement_percent': percentage(measured.get('achievement')),
                    'status': activity_status, 'status_label': status_labels[activity_status],
                    'work_orders': related_orders,
                    'planned_start_date': scheduled.get('planned_start_date'),
                    'planned_end_date': scheduled.get('planned_end_date'),
                    'planned_duration': scheduled.get('planned_duration'),
                })

            project_progress = percentage(center.get('progress'))
            context = {
                'page_title': 'تقرير التنفيذ والإنجاز', 'center': center, 'options': options,
                'filters': params, 'export_query': request.GET.urlencode(), 'activity_rows': activity_rows,
                'phase_rows': list(phase_rows.values()), 'risks': risks, 'exceptions': exceptions,
                'work_orders': work_orders, 'work_order_status': params.get('status', ''),
                'summary': {
                    'progress_percent': project_progress,
                    'completed': sum(row['status'] == 'completed' for row in activity_rows),
                    'in_progress': sum(row['status'] == 'in_progress' for row in activity_rows),
                    'delayed': None,
                },
                'data_note': 'التأخير يتطلب خطاً زمنياً أساسياً معتمداً وبيانات إنجاز زمنية؛ لا يوفرهما عقد التقرير الحالي. الكمية المتبقية وصفية = المخطط − الفعلي لكل نشاط وبالوحدة نفسها.',
                'period_basis': center.get('period_basis'),
            }
            request.core_identity=client.get('/auth/me')
            request.core_modules=client.get('/modules')
            return render(request, 'pm/execution_report.html', context)
        if kind == 'productivity':
            schedule = client.get(root + '/reporting/schedule', params=params).get('items', [])
            progress_by_activity = {row.get('activity_code'): row for row in progress}
            work_orders = client.get(root + '/reporting/work-orders', params=params).get('items', [])
            orders_by_activity = {}
            for order in work_orders:
                orders_by_activity.setdefault(order.get('activity_code'), []).append(order)

            def decimal_or_none(value):
                try:
                    return Decimal(str(value)) if value not in (None, '') else None
                except (InvalidOperation, TypeError, ValueError):
                    return None

            productivity_rows = []
            for item in schedule:
                code = item.get('activity_code')
                progress_row = progress_by_activity.get(code, {})
                quantity = decimal_or_none(progress_row.get('actual_quantity'))
                hours = decimal_or_none(item.get('actual_hours') or item.get('execution_hours') or item.get('work_hours'))
                target = decimal_or_none(item.get('productivity') or item.get('target_productivity'))
                actual = quantity / hours if quantity is not None and hours is not None and hours > 0 else None
                achievement = (actual / target * 100) if actual is not None and target is not None and target > 0 else None
                measurable = actual is not None
                classified = achievement is not None
                status = 'achieved' if classified and achievement >= 100 else 'below' if classified else 'incomplete'
                productivity_rows.append({
                    'code': code or '—', 'name': item.get('name') or '—',
                    'phase': item.get('phase_code') or '—', 'task': item.get('task_code') or '—',
                    'quantity': str(quantity) if quantity is not None else None,
                    'hours': str(hours) if hours is not None and hours >= 0 else None,
                    'time_type': item.get('productivity_time_type') or item.get('hours_type') or 'غير محدد',
                    'target': str(target) if target is not None else None,
                    'actual': str(actual.quantize(Decimal('0.01'))) if actual is not None else None,
                    'achievement': str(achievement.quantize(Decimal('0.01'))) if achievement is not None else None,
                    'unit': item.get('productivity_unit') or 'غير محدد', 'status': status,
                    'status_label': 'حقق المستهدف' if status == 'achieved' else 'أقل من المستهدف' if status == 'below' else 'بيانات غير مكتملة',
                    'reason': item.get('productivity_reason') or item.get('notes') or 'السبب غير مسجل',
                    'orders': len(orders_by_activity.get(code, [])),
                    'source': item.get('source') or 'مصدر التخطيط/التنفيذ',
                })
            comparable = [row for row in productivity_rows if row['target'] and row['actual'] and row['unit'] != 'غير محدد']
            context = {
                'page_title': 'تقرير الأداء والإنتاجية', 'center': center, 'options': options,
                'filters': params, 'export_query': request.GET.urlencode(),
                'productivity_rows': productivity_rows, 'comparison_rows': comparable,
                'trend_rows': [], 'improvement_rows': [row for row in productivity_rows if row['status'] == 'below'],
                'summary': {
                    'measurable': sum(row['actual'] is not None for row in productivity_rows),
                    'achieved': sum(row['status'] == 'achieved' for row in productivity_rows),
                    'below': sum(row['status'] == 'below' for row in productivity_rows),
                    'incomplete': sum(row['status'] == 'incomplete' for row in productivity_rows),
                },
                'data_note': 'تُحسب الإنتاجية فقط عند توفر كمية إنجاز معتمدة وزمن فعلي صالح من النوع نفسه. لا تُعد ساعات العمل المخططة بديلاً عن الزمن الفعلي.',
            }
            if request.GET.get('download') == 'json':
                result = HttpResponse(json.dumps({'project': center.get('name'), 'filters': params,
                    'summary': context['summary'], 'items': productivity_rows}, ensure_ascii=False, indent=2),
                    content_type='application/json; charset=utf-8')
                result['Content-Disposition'] = 'attachment; filename="productivity-report.json"'
                return result
            request.core_identity=client.get('/auth/me')
            request.core_modules=client.get('/modules')
            return render(request, 'pm/productivity_report.html', context)
        extra=client.get(root+'/reporting/'+kind,params=params)
        if kind == 'schedule':
            planning_items = extra.get('items', [])
            def option_label(code, values):
                for option in values:
                    label = str(option.get('name') or '')
                    if label.startswith(str(code)):
                        return label
                return code or 'غير محدد'
            planning_rows = []
            seen_phases = set()
            seen_tasks = set()
            for item in planning_items:
                phase_code = item.get('phase_code') or '—'
                task_code = item.get('task_code') or '—'
                if phase_code not in seen_phases:
                    seen_phases.add(phase_code)
                    planning_rows.append({'kind': 'phase', 'code': phase_code,
                                          'name': option_label(phase_code, options.get('phases', [])),
                                          'phase_code': phase_code})
                task_key = (phase_code, task_code)
                if task_key not in seen_tasks:
                    seen_tasks.add(task_key)
                    planning_rows.append({'kind': 'task', 'code': task_code,
                                          'name': option_label(task_code, options.get('tasks', [])),
                                          'phase_code': phase_code, 'task_code': task_code})
                activity = dict(item)
                activity.update(kind='activity', phase_code=phase_code, task_code=task_code,
                                code=item.get('activity_code') or '—')
                planning_rows.append(activity)
            dated_items = []
            for item in planning_items:
                try:
                    start = date.fromisoformat(item.get('planned_start_date') or '')
                    end = date.fromisoformat(item.get('planned_end_date') or '')
                    if end < start:
                        raise ValueError
                except (TypeError, ValueError):
                    continue
                dated_items.append((item, start, end))
            timeline_start = min((start for _, start, _ in dated_items), default=None)
            timeline_end = max((end for _, _, end in dated_items), default=None)
            timeline_span = ((timeline_end - timeline_start).days + 1) if timeline_start and timeline_end else 1
            timeline_rows = []
            for item, start, end in dated_items:
                timeline_rows.append({
                    'name': item.get('name') or item.get('activity_code') or '—',
                    'code': item.get('activity_code') or '—',
                    'phase_code': item.get('phase_code') or '—',
                    'planned_start_date': start.isoformat(),
                    'planned_end_date': end.isoformat(),
                    'planned_left': round((start - timeline_start).days / timeline_span * 100, 2),
                    'planned_width': round(((end - start).days + 1) / timeline_span * 100, 2),
                    'actual_start_date': item.get('actual_start_date'),
                    'actual_end_date': item.get('actual_end_date'),
                    'is_late': bool(item.get('actual_end_date') and item.get('actual_end_date') > end.isoformat()),
                })
            overdue_rows = [row for row in timeline_rows if row['actual_end_date'] and row['actual_end_date'] > row['planned_end_date']]
            def as_decimal(value):
                try:
                    return Decimal(str(value or '0'))
                except (InvalidOperation, TypeError, ValueError):
                    return Decimal('0')
            planned_hours = sum(
                (as_decimal(item.get('planned_duration')) for item in planning_items),
                Decimal('0'),
            )
            context = {
                'page_title': 'تقرير تخطيط المشروع',
                'center': center,
                'center_code': center.get('project_code') or center.get('code') or '—',
                'center_status': center.get('status') or 'غير محدد',
                'filters': params,
                'options': options,
                'planning_rows': planning_rows,
                'timeline_rows': timeline_rows,
                'timeline_start': timeline_start,
                'timeline_end': timeline_end,
                'overdue_rows': overdue_rows,
                'planning_summary': {
                    'phases': len(options.get('phases', [])),
                    'tasks': len(options.get('tasks', [])),
                    'activities': len(options.get('activities', [])),
                    'planned_hours': planned_hours,
                },
                'export_query': request.GET.urlencode(),
            }
            request.core_identity=client.get('/auth/me')
            request.core_modules=client.get('/modules')
            return render(request, 'pm/planning_report.html', context)
        columns=list(extra['items'][0]) if extra['items'] else []
        rows=[[row.get(key,'') for key in columns] for row in extra['items']]
        request.core_identity=client.get('/auth/me')
        request.core_modules=client.get('/modules')
        return render(request,'pm/reporting.html',{'page_title':'تقارير المشروع','center':center,'costs':costs,
            'progress':progress,'filters':params,'export_query':request.GET.urlencode(), 'options':options,
            'reports':REPORTS.items(),'report_kind':kind,'report_title':REPORTS[kind],
            'columns':[LABELS.get(key,key) for key in columns],'rows':rows,
            'schedule_note':kind=='schedule'})
    except UnauthorizedException:
        return redirect('auth:login')
    except ForbiddenException:
        return HttpResponse('ليس لديك صلاحية تقارير المشروع',status=403)
    except NotFoundException:
        return HttpResponse('المشروع أو عنصر التصفية غير متاح ضمن نطاقك',status=404)
    except ValidationException:
        return HttpResponse('تحقق من تواريخ التصفية والحقول المدخلة',status=400)
    except ApiException:
        return HttpResponse('تعذر تحميل التقرير؛ حاول مجددًا',status=503)
