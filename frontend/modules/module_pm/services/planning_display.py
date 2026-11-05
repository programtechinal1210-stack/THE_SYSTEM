"""Presentation summaries of authorized API facts; no new financial storage."""
from decimal import Decimal,localcontext
from datetime import date

def cash_summary(rows):
    with localcontext() as ctx:
        ctx.prec=120
        periods={}
        for row in rows:
            period=str(row.get('period') or 'غير محددة')
            # Normalize ISO dates to months; never guess legacy/free-text periods.
            try:period=date.fromisoformat(period).strftime('%Y-%m')
            except ValueError:pass
            values=periods.setdefault(period,{'inflow':Decimal(0),'outflow':Decimal(0)})
            values[row['cash_flow_type']]+=Decimal(row['amount_converted'])
        maximum=max((v[k] for v in periods.values() for k in ('inflow','outflow')),default=Decimal(0)) or Decimal(1)
        result=[]
        for period,values in sorted(periods.items()):
            result.append({'period':period,**{k:str(v) for k,v in values.items()},'net':str(values['inflow']-values['outflow']),
                'in_width':str((values['inflow']/maximum*100).quantize(Decimal('.01'))),
                'out_width':str((values['outflow']/maximum*100).quantize(Decimal('.01')))})
        inflow=sum((v['inflow'] for v in periods.values()),Decimal(0));outflow=sum((v['outflow'] for v in periods.values()),Decimal(0))
        return {'periods':result,'inflow':str(inflow),'outflow':str(outflow),'net':str(inflow-outflow)}

def timeline(rows):
    dated=[];missing=[]
    for row in rows:
        try:
            start=date.fromisoformat(row.get('planned_start_date') or '')
            end=date.fromisoformat(row.get('planned_end_date') or '')
            if end<start:raise ValueError()
            dated.append((row,start,end))
        except ValueError:missing.append(row['name'])
    if not dated:return {'bars':[],'missing':missing}
    first=min(s for _,s,_ in dated);last=max(e for _,_,e in dated);span=(last-first).days+1
    bars=[{'name':r['name'],'activity_code':r.get('activity_code',''),'start':s,'end':e,
        'left':round((s-first).days/span*100,2),'width':round(((e-s).days+1)/span*100,2)} for r,s,e in dated]
    bars.sort(key=lambda bar:(bar['start'],bar['end'],str(bar.get('name') or '').casefold()))
    return {'start':first,'end':last,'missing':missing,'bars':bars}


def document_timeline(rows):
    """Return a print-ready, chronological schedule without confusing bar width with duration."""
    result = timeline(rows)
    bars = [
        {
            'name': bar['name'],
            'start': bar['start'],
            'end': bar['end'],
            'left': bar['left'],
            'width': bar['width'],
            'duration_days': (bar['end'] - bar['start']).days + 1,
        }
        for bar in result['bars']
    ]
    bars.sort(key=lambda bar: (bar['start'], bar['end'], str(bar.get('name') or '').casefold()))
    return {
        **result,
        'bars': bars,
        'scheduled_activity_count': len(bars),
        'activity_count': len(rows),
        'missing_count': len(result['missing']),
        'span_days': (result['end'] - result['start']).days + 1 if bars else None,
    }


def schedule_dependency_warnings(activities, dependencies):
    relations = {
        'finish_to_start': ('نهاية إلى بداية', 'planned_start_date', 'planned_end_date',
                            'تبدأ قبل نهاية النشاط السابق'),
        'start_to_start': ('بداية إلى بداية', 'planned_start_date', 'planned_start_date',
                           'تبدأ قبل بداية النشاط السابق'),
        'finish_to_finish': ('نهاية إلى نهاية', 'planned_end_date', 'planned_end_date',
                             'تنتهي قبل نهاية النشاط السابق'),
        'start_to_finish': ('بداية إلى نهاية', 'planned_end_date', 'planned_start_date',
                            'تنتهي قبل بداية النشاط السابق'),
    }
    by_id = {str(row.get('id', '')).replace('-', '').lower(): row for row in activities}
    warnings = []
    for dependency in dependencies:
        relation = relations.get(dependency.get('dependency_type'))
        predecessor = by_id.get(str(dependency.get('predecessor_id', '')).replace('-', '').lower())
        successor = by_id.get(str(dependency.get('successor_id', '')).replace('-', '').lower())
        if not relation or not predecessor or not successor:
            continue
        label, successor_field, predecessor_field, message = relation
        try:
            predecessor_date = date.fromisoformat(predecessor.get(predecessor_field) or '')
            successor_date = date.fromisoformat(successor.get(successor_field) or '')
        except (TypeError, ValueError):
            continue
        if successor_date < predecessor_date:
            warnings.append({
                'predecessor_name': predecessor['name'],
                'successor_name': successor['name'],
                'relation_label': label,
                'message': message,
            })
    return warnings
