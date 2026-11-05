"""Compose existing planning/report facts without introducing another Actual source."""
from decimal import Decimal
from uuid import UUID
from .planning import allowed
from shared.services.api_client import ForbiddenException, NotFoundException


def enrich(client, identity, item, groups, context):
    root='/pm/projects/'+str(UUID(item['id']))
    context['project_root']=root+'/'
    context['activity_count']=len(groups['activities'])
    context['actual_available']=False
    progress={};costs={}
    if allowed(identity,'pm.reports.view'):
        try:
            center=client.get(root+'/command-center')
            context['center']=center
            context['actual_available']=True
            progress={r['activity_code']:r for r in client.get(root+'/reporting/progress')['items']}
            costs={r['activity_code']:r for r in client.get(root+'/reporting/cost')['items']}
            if center['progress'] is not None:
                context['progress_percent']=str((Decimal(center['progress'])*100).quantize(Decimal('.1')))
        except (ForbiddenException, NotFoundException):
            pass
    rows=[]
    for phase in groups['phases']:
        for kind,row,depth,parent in [('phases',phase,0,'')]:
            rows.append(dict(row,kind=kind,depth=depth,parent=parent,type_label='مرحلة',code=row['phase_code']))
        for task in phase['children']:
            rows.append(dict(task,kind='tasks',depth=1,parent=phase['id'],type_label='مهمة',code=task['task_code']))
            for activity in task['children']:
                rows.append(dict(activity,kind='activities',depth=2,parent=task['id'],type_label='نشاط',code=activity['activity_code']))
    context['work_rows']=rows
    for row in rows:
        acts=([row] if row['kind']=='activities' else row['children'] if row['kind']=='tasks'
              else [a for t in row['children'] for a in t['children']])
        facts=[progress[a['activity_code']] for a in acts if a['activity_code'] in progress]
        if facts and len({r['unit'] for r in facts})==1:
            planned=sum(Decimal(r['planned_quantity']) for r in facts)
            actual=sum(Decimal(r['actual_quantity']) for r in facts)
            if planned:
                row['progress_percent']=str((actual/planned*100).quantize(Decimal('.1')))
                row['progress_width']=str(max(Decimal(0),min(Decimal(100),actual/planned*100)))
        if context['actual_available']:
            row['actual_cost']=str(sum(Decimal(costs[a['activity_code']]['actual_cost']) for a in acts if a['activity_code'] in costs))
