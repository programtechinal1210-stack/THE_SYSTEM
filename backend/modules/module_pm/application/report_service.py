"""Project reports and command center — read-only analytics over PM sources."""
import json
from decimal import Decimal, ROUND_HALF_EVEN, localcontext

from sqlalchemy import text
from fastapi import HTTPException
from core.access import require

from .planning_service import PlanningService
from ..domain.planning import cost, total as money_total, in_scope
from ..domain.reporting import ReportFilters


def precise_sum(values):
    with localcontext() as context:
        context.prec=120
        return sum(values,Decimal(0))


def achievement(actual,planned):
    if not planned:return None
    with localcontext() as context:
        context.prec=120
        return str((actual/planned).quantize(Decimal('.0001'),rounding=ROUND_HALF_EVEN))


class ReportService(PlanningService):
    async def activities(self,project_id,filters):
        rows=[r for r in await self.repo.rows('activities',project_id) if not r['deleted_at']]
        phases={r['id']:r for r in await self.repo.rows('phases',project_id) if not r['deleted_at']}
        tasks={r['id']:r for r in await self.repo.rows('tasks',project_id) if not r['deleted_at'] and r['phase_id'] in phases}
        rows=[r for r in rows if r['task_id'] in tasks]
        for kind,value in [('phases',filters.phase_id),('tasks',filters.task_id),('activities',filters.activity_id)]:
            if value:
                selected=await self.repo.get(kind,value.hex)
                if not selected or selected['project_id']!=project_id or selected['deleted_at']:
                    raise HTTPException(404,'Report hierarchy filter unavailable')
        return [r for r in rows if (not filters.phase_id or tasks[r['task_id']]['phase_id']==filters.phase_id.hex)
                and (not filters.task_id or r['task_id']==filters.task_id.hex)
                and (not filters.activity_id or r['id']==filters.activity_id.hex)]

    def execution_filter(self,filters,date_column):
        clauses=['w.deleted_at IS NULL']
        params={}
        if filters.status:
            clauses.append('w.status=:status'); params['status']=filters.status
        else:
            clauses.append("w.status != 'rejected'")
        for field,operator in [('date_from','>='),('date_to','<=')]:
            value=getattr(filters,field)
            if value:
                clauses.append(f'substr({date_column},1,10){operator}:{field}')
                params[field]=value.isoformat()
        return ' AND '.join(clauses),params
    async def _count(self, table, project_id, where=''):
        return await self.session.scalar(text(
            f'SELECT COUNT(*) FROM {table} WHERE project_id=:p AND deleted_at IS NULL {where}'),
            {'p': project_id})

    async def _activity_actual_cost(self, activity_id, filters=None):
        clause,params=self.execution_filter(filters or ReportFilters(),'c.created_at')
        rows = (await self.session.execute(text(
            'SELECT c.quantity,c.unit_price,c.exchange_rate_snapshot FROM pm_work_order_consumptions c '
            'JOIN pm_work_orders w ON w.id=c.work_order_id AND w.project_id=c.project_id '
            'WHERE w.activity_id=:a AND c.deleted_at IS NULL AND '+clause),dict(params,a=activity_id))).mappings()
        return precise_sum(cost(r['quantity'],r['unit_price'],json.loads(r['exchange_rate_snapshot'])['rate']) for r in rows)

    async def _activity_actual_quantity(self, activity_id, filters=None):
        filters=filters or ReportFilters()
        dated=bool(filters.date_from or filters.date_to)
        clause,params=self.execution_filter(filters,'e.recorded_at')
        if dated:
            sql='SELECT e.delta FROM pm_execution_quantity_events e JOIN pm_work_orders w ON w.id=e.work_order_id AND w.project_id=e.project_id '
        else:
            sql='SELECT w.actual_quantity_snapshot FROM pm_work_orders w '
        rows = (await self.session.execute(text(
            sql+'WHERE w.activity_id=:a AND '+clause),dict(params,a=activity_id))).scalars()
        return precise_sum(Decimal(r) for r in rows)

    async def command_center(self, project_id, filters=None):
        filters=filters or ReportFilters()
        await self.project(project_id, 'pm.reports.view')
        project = await self.repo.get('projects', project_id)
        costs=(await self.cost_report(project_id,filters))['items']
        quantities=(await self.progress_report(project_id,filters))['items']
        planned_cost=money_total(r['planned_cost'] for r in costs)
        actual_cost=money_total(r['actual_cost'] for r in costs)
        planned_quantity=precise_sum(Decimal(r['planned_quantity']) for r in quantities)
        actual_quantity=precise_sum(Decimal(r['actual_quantity']) for r in quantities)
        units={r['unit'] for r in quantities}
        comparable=len(units)<=1
        progress=achievement(actual_quantity,planned_quantity) if comparable else None
        return {
            'project_code': project['project_code'], 'name': project['name'], 'status': project['status'],
            'currency': project['currency'],
            'filters':filters.model_dump(mode='json'),
            'period_basis':'UTC event/consumption recording date; planned values remain current-plan context',
            'counts_scope':'Entire project; execution amount filters do not change governance counts',
            'planned_cost': str(planned_cost), 'actual_cost': str(actual_cost),
            'cost_variance': str(precise_sum([planned_cost,actual_cost.copy_negate()])),
            'planned_quantity': str(planned_quantity) if comparable else None,
            'actual_quantity': str(actual_quantity) if comparable else None,
            'progress': progress,
            'quantities_by_unit':[{'unit':unit,
                'planned_quantity':str(precise_sum(Decimal(r['planned_quantity']) for r in quantities if r['unit']==unit)),
                'actual_quantity':str(precise_sum(Decimal(r['actual_quantity']) for r in quantities if r['unit']==unit))} for unit in sorted(units)],
            'risks': await self._count('pm_risks', project_id),
            'open_risks': await self._count('pm_risks', project_id, "AND status='active'"),
            'deviations': await self._count('pm_deviations', project_id),
            'open_deviations': await self._count('pm_deviations', project_id, "AND status='open'"),
            'work_orders': await self._count('pm_work_orders', project_id),
            'weekly_plans': await self._count('pm_weekly_plans', project_id),
        }

    async def cost_report(self, project_id, filters=None):
        filters=filters or ReportFilters()
        project = await self.project(project_id, 'pm.reports.view')
        activities = await self.activities(project_id,filters)
        items = []
        for a in activities:
            presented = await self.present('activities', a)
            planned = cost(presented['planned_cost'], 1, presented['exchange_rate_snapshot']['rate'])
            items.append({'activity_code': a['activity_code'], 'planned_cost': str(planned),
                          'currency': project['currency'],
                          'actual_cost': str(await self._activity_actual_cost(a['id'],filters))})
        return {'currency': project['currency'], 'items': items}

    async def progress_report(self, project_id, filters=None):
        filters=filters or ReportFilters()
        await self.project(project_id, 'pm.reports.view')
        activities = await self.activities(project_id,filters)
        items = []
        for a in activities:
            planned = Decimal(a['planned_quantity'])
            actual = await self._activity_actual_quantity(a['id'],filters)
            items.append({'activity_code': a['activity_code'], 'planned_quantity': str(planned),
                          'actual_quantity': str(actual), 'achievement': achievement(actual,planned),'unit':a['unit']})
        return {'items': items}

    async def export(self, project_id, filters=None,risk_status=None,severity=None,query=None):
        await self.project(project_id, 'pm.reports.view')
        center = await self.command_center(project_id,filters)
        result={'command_center': center,
                'cost': (await self.cost_report(project_id,filters))['items'],
                'progress': (await self.progress_report(project_id,filters))['items']}
        for kind in ('executive','hierarchy','schedule','risk','resources','work-orders','exceptions'):
            result[kind]=await self.supporting_report(
                project_id,kind,filters,
                risk_status=risk_status if kind=='risk' else None,
                severity=severity if kind=='risk' else None,
                query=query if kind=='risk' else None)
        return result

    async def supporting_report(self,project_id,kind,filters=None,risk_status=None,severity=None,query=None):
        f=filters or ReportFilters()
        project=await self.project(project_id,'pm.reports.view')
        activities=await self.activities(project_id,f)
        acts={a['id']:a for a in activities}
        tasks={r['id']:r for r in await self.repo.rows('tasks',project_id)}
        phases={r['id']:r for r in await self.repo.rows('phases',project_id)}
        items=[]
        note=None
        if kind=='options':
            return {'phases':[{'id':r['id'],'name':r['phase_code']+' — '+r['name']} for r in phases.values() if not r['deleted_at']],
                    'tasks':[{'id':r['id'],'name':r['task_code']+' — '+r['name']} for r in tasks.values() if not r['deleted_at']],
                    'activities':[{'id':r['id'],'name':r['activity_code']+' — '+r['name']} for r in activities]}
        if kind=='executive':
            items=[await self.command_center(project_id,f)]
        elif kind in ('hierarchy','schedule'):
            dependencies=(await self.session.execute(text('SELECT predecessor_id,successor_id FROM pm_activity_dependencies WHERE project_id=:p'),{'p':project_id})).mappings().all()
            for a in activities:
                task=tasks[a['task_id']];phase=phases[task['phase_id']]
                items.append({'phase_code':phase['phase_code'],'task_code':task['task_code'],'activity_code':a['activity_code'],
                    'name':a['name'],'planned_quantity':a['planned_quantity'],'unit':a['unit'],'planned_duration':a['planned_duration'],
                    'planned_start_date':a.get('planned_start_date'),'planned_end_date':a.get('planned_end_date'),
                    'predecessors':', '.join(acts[r['predecessor_id']]['activity_code'] for r in dependencies if r['successor_id']==a['id'] and r['predecessor_id'] in acts)})
            if kind=='schedule':note='Recorded activity dates only; missing dates remain unspecified. Durations are effort hours, not a computed critical path.'
        elif kind=='resources':
            for r in await self.repo.rows('requirements',project_id):
                if r['deleted_at'] or r['activity_id'] not in acts:continue
                a=acts[r['activity_id']]
                amount=cost(r['quantity'],r['unit_price'],json.loads(r['exchange_rate_snapshot'])['rate'])
                amount=cost(amount,1,json.loads(a['exchange_rate_snapshot'])['rate'])
                items.append({'requirement_code':r['requirement_code'],'activity_code':a['activity_code'],'name':r['name'],
                    'quantity':r['quantity'],'unit':r['unit'],'planned_cost':str(amount),'currency':project['currency']})
        elif kind=='risk':
            rows=(await self.session.execute(text(
                'SELECT r.*, ph.phase_code, ph.name AS phase_name, '
                't.task_code, t.name AS task_name, a.activity_code, a.name AS activity_name, '
                'u.full_name AS owner_name FROM pm_risks r '
                'LEFT JOIN pm_phases ph ON ph.id=r.phase_id AND ph.project_id=r.project_id AND ph.deleted_at IS NULL '
                'LEFT JOIN pm_tasks t ON t.id=r.task_id AND t.project_id=r.project_id AND t.deleted_at IS NULL '
                'LEFT JOIN pm_activities a ON a.id=r.activity_id AND a.project_id=r.project_id AND a.deleted_at IS NULL '
                'LEFT JOIN users u ON u.id=r.owner_user_id '
                'WHERE r.project_id=:p AND r.deleted_at IS NULL'),{'p':project_id})).mappings()
            for r in rows:
                activity=acts.get(r['activity_id'])
                risk_task=r['task_id'] or (activity.get('task_id') if activity else None)
                task=tasks.get(risk_task)
                risk_phase=r['phase_id'] or (task.get('phase_id') if task else None)
                if f.phase_id and risk_phase!=f.phase_id.hex:continue
                if f.task_id and risk_task!=f.task_id.hex:continue
                if f.activity_id and r['activity_id']!=f.activity_id.hex:continue
                day=str(r['discovery_date'] or r['created_at'])[:10]
                if f.date_from and day<f.date_from.isoformat() or f.date_to and day>f.date_to.isoformat():continue
                if risk_status and r['status']!=risk_status:continue
                importance=Decimal(str(r['importance'] or 0))
                risk_severity='high' if importance>=Decimal('12') else 'medium' if importance>=Decimal('5') else 'low'
                if severity and risk_severity!=severity:continue
                row={key:r[key] for key in (
                    'risk_code','description','classification','level','phase_code','phase_name',
                    'task_code','task_name','activity_code','activity_name','status','probability',
                    'impact','importance','corrective_action','owner_name','discovery_date',
                    'created_at','updated_at')}
                if query and query.casefold() not in ' '.join(str(value or '') for value in row.values()).casefold():continue
                row['name']=r['name']
                items.append(row)
            items.sort(key=lambda row: (Decimal(str(row.get('importance') or 0)), str(row.get('risk_code') or '')), reverse=True)
            note='تُحدد الفترة بتاريخ اكتشاف الخطر أو تاريخ إنشائه عند غياب تاريخ الاكتشاف. لا يحتفظ النظام بتاريخ تغير الحالة لإعادة بناء المخاطر القائمة تاريخياً.'
        elif kind=='work-orders':
            rows=(await self.session.execute(text('SELECT * FROM pm_work_orders WHERE project_id=:p AND deleted_at IS NULL'),{'p':project_id})).mappings()
            for r in rows:
                if r['activity_id'] not in acts or (f.status and r['status']!=f.status):continue
                if not f.status and r['status']=='rejected':continue
                clause,params=self.execution_filter(f,'c.created_at')
                resources=(await self.session.execute(text('SELECT c.quantity,c.unit_price,c.exchange_rate_snapshot FROM pm_work_order_consumptions c JOIN pm_work_orders w ON w.id=c.work_order_id WHERE w.id=:id AND c.deleted_at IS NULL AND '+clause),dict(params,id=r['id']))).mappings()
                amount=precise_sum(cost(c['quantity'],c['unit_price'],json.loads(c['exchange_rate_snapshot'])['rate']) for c in resources)
                quantity=r['actual_quantity_snapshot']
                if f.date_from or f.date_to:
                    clause,params=self.execution_filter(f,'e.recorded_at')
                    events=(await self.session.execute(text('SELECT e.delta FROM pm_execution_quantity_events e JOIN pm_work_orders w ON w.id=e.work_order_id WHERE w.id=:id AND '+clause),dict(params,id=r['id']))).scalars()
                    quantity=str(precise_sum(Decimal(v) for v in events))
                items.append({'work_order_code':r['work_order_code'],'activity_code':acts[r['activity_id']]['activity_code'],
                    'status':r['status'],'actual_quantity':quantity,'actual_cost':str(amount),'currency':project['currency']})
        elif kind=='exceptions':
            for r in (await self.cost_report(project_id,f))['items']:
                if Decimal(r['actual_cost'])>Decimal(r['planned_cost']):
                    items.append({'code':r['activity_code'],'exception':'cost_overrun','planned_cost':r['planned_cost'],'actual_cost':r['actual_cost'],'currency':r['currency']})
        else:
            raise HTTPException(404,'Report unavailable')
        return {'items':items,'currency':project['currency'],'note':note,'filters':f.model_dump(mode='json')}

    async def portfolio(self,status=None):
        require(self.request,'pm.reports.view')
        scopes=self.request.state.permission_scopes.get('pm.reports.view',{'self'})
        items=[]
        for project in await self.repo.rows('projects'):
            if project['deleted_at'] or status and project['status']!=status:continue
            if not in_scope(project,self.request.state.user,self.request.state.is_admin,scopes):continue
            items.append(dict(await self.command_center(project['id']),project_id=project['id']))
        return {'items':items,'note':'Monetary totals remain separate by project currency.'}
