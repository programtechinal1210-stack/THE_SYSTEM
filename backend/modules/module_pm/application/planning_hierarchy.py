"""Hierarchy commands keep identity and historical snapshots stable."""
import hashlib
import json
from fastapi import HTTPException
from sqlalchemy import text
from ..domain.planning import KINDS,Phase,Task
from .planning_service import PlanningService,now


class PlanningHierarchy(PlanningService):
    async def inspect(self,project_id,command):
        project=await self.project(project_id,'pm.planning.manage')
        if project['status'] in ('in_progress','completed'):
            raise HTTPException(409,'لا يمكن إعادة هيكلة خطة قيد التنفيذ')
        kind=command.kind
        row=await self.entity(kind,project_id,command.entity_id.hex,'update')
        rows=[r for r in await self.repo.rows(kind,project_id) if not r['deleted_at']]
        fk=KINDS[kind][4]
        if command.operation=='move':
            if kind=='phases' or not command.target_id:
                raise HTTPException(422,'اختر أبًا جديدًا داخل المشروع')
            target=await self.repo.get(KINDS[kind][3],command.target_id.hex)
            if not target or target['deleted_at'] or target['project_id']!=project_id:
                raise HTTPException(422,'الهدف يجب أن يكون نشطًا داخل المشروع نفسه')
            if target['id']==row[fk]:raise HTTPException(409,'العنصر موجود تحت هذا الأب بالفعل')
        elif command.operation=='promote':
            if kind not in ('tasks','activities'):
                raise HTTPException(409,'ترقية المرحلة إلى مشروع تتطلب معالجة حدود المشروع والروابط العابرة أولًا')
            if not command.new_name.strip():
                raise HTTPException(422,'حدد رمز واسم العنصر الأب الجديد')
        elif command.operation in ('before','after'):
            target=await self.repo.get(kind,command.target_id.hex) if command.target_id else None
            if not target or target['deleted_at'] or target['project_id']!=project_id or target[fk]!=row[fk] or target['id']==row['id']:
                raise HTTPException(422,'إعادة الترتيب تتطلب عنصرًا آخر تحت الأب نفسه')
        elif command.operation not in ('up','down'):
            raise HTTPException(422,'عملية غير مدعومة')
        # Capture the full active tree so a second user cannot invalidate a preview silently.
        tree={k:[r for r in await self.repo.rows(k,project_id) if not r['deleted_at']] for k in ('phases','tasks','activities','requirements')}
        token=hashlib.sha256(json.dumps({'command':command.model_dump(mode='json',exclude={'preview_token'}),'project':project,'tree':tree},sort_keys=True).encode()).hexdigest()
        return {'preview_token':token,'name':row['name'],'code':row[KINDS[kind][2]],
            'operation':command.operation,'identity_preserved':True,'business_code_preserved':True,
            'history_preserved':True,'row':row,'siblings':[r for r in rows if r[fk]==row[fk]]}

    async def apply(self,project_id,command):
        preview=await self.inspect(project_id,command)
        if command.preview_token!=preview['preview_token']:
            raise HTTPException(409,'تغيرت الخطة؛ أعد معاينة العملية قبل اعتمادها')
        row=preview['row'];kind=command.kind;fk=KINDS[kind][4]
        if command.operation in ('up','down','before','after'):
            siblings=preview['siblings'];index=next(i for i,r in enumerate(siblings) if r['id']==row['id'])
            if command.operation in ('before','after'):
                siblings.pop(index)
                other=next(i for i,r in enumerate(siblings) if r['id']==command.target_id.hex)
                siblings.insert(other+(command.operation=='after'),row)
            else:
                other=index+(-1 if command.operation=='up' else 1)
                if other<0 or other>=len(siblings):raise HTTPException(409,'العنصر عند حد القائمة')
                siblings[index],siblings[other]=siblings[other],siblings[index]
            for position,sibling in enumerate(siblings):
                await self.repo.save(kind,sibling['id'],{'sort_order':position,'updated_at':now()})
        else:
            target=command.target_id.hex if command.target_id else None
            if command.operation=='promote':
                if kind=='tasks':
                    parent=await self.save('phases',project_id,Phase(phase_code=command.new_code,name=command.new_name,owner_user_id=row.get('owner_user_id')))
                else:
                    old_parent=await self.repo.get('tasks',row['task_id'])
                    parent=await self.save('tasks',project_id,Task(task_code=command.new_code,name=command.new_name,phase_id=old_parent['phase_id']))
                target=parent['id']
            await self.repo.save(kind,row['id'],{fk:target,'sort_order':0,'updated_at':now()})
            condition='id=:id' if kind=='activities' else 'task_id=:id'
            await self.session.execute(text('UPDATE pm_activities SET approval_status=\'pending\', approved_by=NULL, approved_at=NULL, approval_reason=\'تغير التسلسل الهرمي\' WHERE '+condition),{'id':row['id']})
            # Denormalized risk/deviation ancestor references follow the live hierarchy, not history.
            if kind=='activities':
                task=await self.repo.get('tasks',target)
                for table in ('pm_risks','pm_deviations'):
                    await self.session.execute(text(f'UPDATE {table} SET task_id=:t,phase_id=:ph WHERE activity_id=:id AND project_id=:p'),
                        {'t':target,'ph':task['phase_id'],'id':row['id'],'p':project_id})
            elif kind=='tasks':
                for table in ('pm_risks','pm_deviations'):
                    await self.session.execute(text(f'UPDATE {table} SET phase_id=:ph WHERE project_id=:p AND (task_id=:id OR activity_id IN (SELECT id FROM pm_activities WHERE task_id=:id))'),
                        {'ph':target,'id':row['id'],'p':project_id})
        result=await self.repo.get(kind,row['id'])
        self.audit(kind,row['id'],row,{'item':result,'hierarchy_operation':command.operation,'preview_token':command.preview_token})
        return result
