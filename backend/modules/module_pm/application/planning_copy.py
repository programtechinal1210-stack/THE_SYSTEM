"""Copy a planning subtree inside its project, using existing validated commands."""
import hashlib
import json
from uuid import uuid4
from fastapi import HTTPException
from .planning_service import PlanningService
from ..domain.planning import KINDS


class PlanningCopy(PlanningService):
    async def preview(self, project_id, command):
        project=await self.project(project_id,'pm.planning.manage')
        if project['status'] in ('in_progress','completed'):
            raise HTTPException(409,'لا يمكن نسخ عناصر داخل خطة قيد التنفيذ')
        source=await self.entity(command.kind,project_id,command.source_id.hex,'update')
        parent_kind=KINDS[command.kind][3]
        target=project if parent_kind=='projects' else await self.entity(parent_kind,project_id,command.parent_id.hex,'update')
        if parent_kind=='projects' and command.parent_id.hex!=project_id:
            raise HTTPException(422,'النسخ متاح داخل المشروع نفسه فقط')
        nodes=[(command.kind,source)]
        next_kind={'phases':'tasks','tasks':'activities','activities':'requirements'}
        children={kind:await self.repo.rows(kind,project_id) for kind in next_kind.values()}
        cursor=0
        while cursor<len(nodes):
            kind,row=nodes[cursor];cursor+=1
            if kind in next_kind:
                child_kind=next_kind[kind]
                for child in children[child_kind]:
                    if not child['deleted_at'] and child[KINDS[child_kind][4]]==row['id']:
                        nodes.append((child_kind,child))
            if len(nodes)>500:
                raise HTTPException(422,'انسخ جزءًا أصغر من الخطة؛ الحد 500 عنصر في العملية')
        data={'project':project,'target':target,'nodes':nodes,'command':command.model_dump(mode='json',exclude={'preview_token'})}
        token=hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()
        return {'preview_token':token,'name':source['name'],'count':len(nodes),
                'nodes':nodes,'target':target,'execution_copied':False,'approval_copied':False}

    async def apply(self,project_id,command):
        preview=await self.preview(project_id,command)
        if preview['preview_token']!=command.preview_token:
            raise HTTPException(409,'تغيرت الخطة؛ أعد المعاينة قبل النسخ')
        mapped={};root=None
        for index,(kind,row) in enumerate(preview['nodes']):
            model=KINDS[kind][1];code_field=KINDS[kind][2];parent_field=KINDS[kind][4]
            data={key:row[key] for key in model.model_fields if key in row}
            data[code_field]=command.new_code if index==0 else command.new_code[:45]+'-'+uuid4().hex[:24]
            data['name']=command.new_name if index==0 else row['name']
            if parent_field in model.model_fields:
                data[parent_field]=command.parent_id.hex if index==0 else mapped[row[parent_field]]
            if 'rate_date' in data:data['rate_date']=command.rate_date.isoformat()
            if 'attachment_url' in data:data['attachment_url']=''
            result=await self.save(kind,project_id,model.model_validate(data))
            mapped[row['id']]=result['id']
            if index==0:root=result
        return {'id':root['id'],'kind':command.kind,'created':len(mapped)}
