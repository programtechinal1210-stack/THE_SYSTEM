"""Explicit project and activity decisions; snapshots remain immutable."""
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy import text
from .planning_service import PlanningService, now


class PlanningWorkflow(PlanningService):
    @staticmethod
    def activities_ready_for_execution(rows):
        return bool(rows) and all(row['approval_status'] == 'approved' for row in rows)

    async def overview(self, project_id):
        project = await self.project(project_id, 'pm.planning.view')
        def key(value):
            return str(value).replace('-', '').lower() if value is not None else None

        phases = {key(r['id']): r for r in await self.repo.rows('phases', project_id) if not r['deleted_at']}
        tasks = {key(r['id']): r for r in await self.repo.rows('tasks', project_id) if not r['deleted_at']}
        requirements = [r for r in await self.repo.rows('requirements', project_id) if not r['deleted_at']]
        requirements_by_activity = {}
        for requirement in requirements:
            requirements_by_activity.setdefault(key(requirement.get('activity_id')), []).append({
                'id': requirement['id'],
                'code': requirement.get('requirement_code'),
                'name': requirement.get('name'),
                'quantity': requirement.get('quantity'),
                'unit': requirement.get('unit'),
                'resource_type': requirement.get('resource_type'),
                'planned_cost': requirement.get('planned_cost'),
                'currency': requirement.get('planned_cost_currency') or requirement.get('currency'),
            })
        rows = []
        for raw in await self.repo.rows('activities', project_id):
            if raw['deleted_at']:
                continue
            activity = await self.present('activities', raw)
            task = tasks.get(key(raw.get('task_id')))
            phase = phases.get(key(task.get('phase_id'))) if task else None
            activity.update({
                'task_name': task.get('name') if task else None,
                'task_code': task.get('task_code') if task else None,
                'phase_name': phase.get('name') if phase else None,
                'phase_code': phase.get('phase_code') if phase else None,
                'hierarchy_valid': bool(task and phase),
                'requirements': requirements_by_activity.get(key(raw['id']), []),
            })
            rows.append(activity)
        stats = {s: sum(r['approval_status']==s for r in rows) for s in ('pending','approved','rejected')}
        stats['total'] = len(rows)
        project['organization_name'] = await self.session.scalar(
            text('SELECT name FROM organizations WHERE id=:id'), {'id': project['organization_id']})
        return {'project':project,'activities':rows,'stats':stats}

    async def decision(self, project_id, activity_id, decision, reason=''):
        project = await self.project(project_id, 'pm.planning.manage')
        if project['status'] not in ('planning','planned'):
            raise HTTPException(409, 'قرارات الإقرار متاحة أثناء التخطيط فقط')
        row = await self.entity('activities',project_id,activity_id,'update')
        current = row['approval_status']
        if decision == 'approved':
            if current != 'pending':
                raise HTTPException(409, 'أعد النشاط إلى المراجعة قبل إقراره')
            detail = await self.present('activities',row)
            if Decimal(row['planned_quantity']) <= 0 or Decimal(detail['planned_cost']) <= 0:
                raise HTTPException(422, 'الإقرار يتطلب كمية وتكلفة احتياجات موجبتين')
        elif decision == 'rejected':
            if current != 'pending' or not reason.strip():
                raise HTTPException(422, 'رفض النشاط يتطلب حالة انتظار وسببًا واضحًا')
        elif decision == 'pending':
            if current not in ('approved','rejected'):
                raise HTTPException(409, 'النشاط قيد المراجعة بالفعل')
        else:
            raise HTTPException(422, 'قرار غير صالح')
        await self.repo.save('activities',activity_id,{'approval_status':decision,'approval_reason':reason.strip(),
            'approved_by':self.request.state.user_id.hex if decision=='approved' else None,
            'approved_at':now() if decision=='approved' else None,'updated_at':now()})
        after=await self.repo.get('activities',activity_id)
        self.audit('activities',activity_id,row,after)
        return after

    async def approve_all(self, project_id):
        project=await self.project(project_id,'pm.planning.manage')
        if project['status'] not in ('planning','planned'):
            raise HTTPException(409,'الإقرار الجماعي متاح أثناء التخطيط فقط')
        rows=[r for r in await self.repo.rows('activities',project_id) if not r['deleted_at'] and r['approval_status']=='pending']
        approved=[]; failed=[]
        for row in rows:
            detail=await self.present('activities',row)
            if Decimal(row['planned_quantity'])<=0 or Decimal(detail['planned_cost'])<=0:
                failed.append({'id':row['id'],'name':row['name'],'reason':'الكمية أو التكلفة غير مكتملة'})
            else:
                await self.decision(project_id,row['id'],'approved')
                approved.append(row['id'])
        self.audit('projects',project_id,None,{'approved_activities':approved,'failed':failed})
        return {'approved':approved,'failed':failed}

    async def transition(self, project_id, target):
        project=await self.project(project_id,'pm.projects.update')
        transitions={'issued':{'planning'},'planning':{'planned'},'planned':{'planning','in_progress'}}
        if target not in transitions.get(project['status'],set()):
            raise HTTPException(409,'انتقال حالة المشروع غير مسموح')
        if target in ('planned','in_progress'):
            rows=[r for r in await self.repo.rows('activities',project_id) if not r['deleted_at']]
            if not rows:
                raise HTTPException(
                    409,
                    'أضف أنشطة قبل إكمال التخطيط' if target == 'planned'
                    else 'أضف أنشطة قبل بدء التنفيذ',
                )
            if not self.activities_ready_for_execution(rows):
                raise HTTPException(
                    409,
                    'يجب إقرار جميع الأنشطة قبل اعتماد الخطة' if target == 'planned'
                    else 'يجب إقرار جميع الأنشطة قبل بدء التنفيذ',
                )
        await self.repo.save('projects',project_id,{'status':target,'updated_at':now()})
        result=await self.repo.get('projects',project_id)
        self.audit('projects',project_id,project,result)
        return result
