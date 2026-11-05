"""Material request and reservation forms; all writes use the Core API client."""
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID, uuid4
from urllib.parse import urlencode
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from shared.services.api_client import ApiClient, ApiException, UnauthorizedException


@require_http_methods(['GET','POST'])
def page(request):
    api=ApiClient(token=request.session.get('access_token'))
    try:
        identity=api.get('/auth/me')
        can=lambda p: identity.get('is_admin') or p in identity.get('permissions',[])
        if not can('inventory.requests.view'):
            return HttpResponse('ليس لديك صلاحية عرض طلبات المواد',status=403)
        work_context=api.get('/profile/work-context')
        organization=work_context.get('selected_id')
        if not organization:
            return HttpResponse('اختر جهة العمل أولاً',status=409)
        identifier=UUID(request.GET['request']).hex if request.GET.get('request') else ''
        base=reverse('inventory:requests')
        selected=request.POST.get('warehouse_id') or request.GET.get('warehouse_id','')
        error=''; posted_lines=[]
        if request.method=='POST':
            command=request.POST.get('command','')
            needed={'save':'inventory.requests.create','submit':'inventory.requests.create','cancel':'inventory.requests.create',
                    'approve':'inventory.requests.approve','reject':'inventory.requests.approve','close':'inventory.requests.approve',
                    'reserve':'inventory.reservations.manage','release':'inventory.reservations.manage','expire':'inventory.reservations.manage'}.get(command)
            if not needed or not can(needed):
                return HttpResponse('ليس لديك صلاحية تنفيذ الإجراء',status=403)
            try:
                if command in ('save','submit') and request.POST.getlist('item_id'):
                    items=request.POST.getlist('item_id'); quantities=request.POST.getlist('quantity')
                    if not 1<=len(items)<=100 or len(items)!=len(quantities): raise ValueError('تحقق من بنود الطلب')
                    posted_lines=[{'item_id':i,'quantity':q} for i,q in zip(items,quantities)]
                    payload={'organization_id':organization,'lines':posted_lines,
                             'request_no':request.POST.get('request_no') or None}
                    saved=api.put('/inventory/requests/'+identifier,payload) if identifier else api.post('/inventory/requests',payload)
                    identifier=saved['id']
                    if command=='submit':
                        api.post('/inventory/requests/'+identifier+'/submit',{})
                elif command=='submit':
                    identifier=UUID(request.POST['request_id']).hex
                    api.post('/inventory/requests/'+identifier+'/submit',{})
                elif command=='save':
                    raise ValueError('أضف بنداً واحداً على الأقل إلى الطلب')
                elif command=='reserve':
                    api.post('/inventory/reservations',{'request_line_id':request.POST.get('request_line_id'),
                        'warehouse_id':selected,'location_id':request.POST.get('location_id') or None,
                        'quantity':request.POST.get('reserve_quantity'),'reservation_key':request.POST.get('reservation_key'),
                        'expires_at':request.POST.get('expires_at') or None})
                elif command in ('release','expire'):
                    api.post('/inventory/reservations/'+UUID(request.POST['reservation_id']).hex+'/'+command,{})
                else:
                    identifier=UUID(request.POST['request_id']).hex
                    payload={'reason':request.POST.get('reason','')}
                    if command=='approve' and request.POST.getlist('approval_line'):
                        payload['approved_quantities']=dict(zip(request.POST.getlist('approval_line'),request.POST.getlist('approved_quantity')))
                    api.post('/inventory/requests/'+identifier+'/'+command,payload)
                return HttpResponseRedirect(base+'?'+urlencode({'request':identifier,'warehouse_id':selected}))
            except (ApiException,ValueError,KeyError) as exc:
                error='تعذر تنفيذ الإجراء: '+str(exc)
        status_filter=request.GET.get('status','')
        search=request.GET.get('search','').strip()
        date_from=request.GET.get('date_from','')
        date_to=request.GET.get('date_to','')
        list_params={'organization_id':organization,'skip':max(0,int(request.GET.get('skip','0'))),'limit':50}
        date_to_api=date_to
        if date_to:
            try:
                date_to_api=(date.fromisoformat(date_to)+timedelta(days=1)).isoformat()
            except ValueError:
                date_to_api=date_to
        for key,value in (('status',status_filter),('search',search),('date_from',date_from),('date_to',date_to_api)):
            if value: list_params[key]=value
        listing=api.get('/inventory/requests',params=list_params)
        records=listing.get('items',[])
        document=api.get('/inventory/requests/'+identifier) if identifier else None
        if document and document['organization_id']!=organization:
            return HttpResponse('الطلب خارج جهة العمل الحالية',status=403)
        warehouses=api.get('/inventory/warehouses',params={'organization_id':organization,'limit':200})['items'] if can('inventory.warehouses.view') else []
        if not selected and warehouses: selected=warehouses[0]['id']
        if selected and selected not in {w['id'] for w in warehouses}:
            return HttpResponse('المخزن خارج جهة العمل الحالية',status=403)
        reservations=api.get('/inventory/reservations',params={'warehouse_id':selected})['items'] if selected and can('inventory.reservations.view') else []
        balances=api.get('/inventory/balances',params={'warehouse_id':selected})['items'] if selected and can('inventory.stock.view') else []
        locations=api.get('/inventory/warehouses/'+selected+'/locations')['items'] if selected and can('inventory.warehouses.view') else []
        items=api.get('/inventory/items',params={'organization_id':organization,'limit':200})['items'] if can('inventory.items.view') else []
        units=api.get('/inventory/units',params={'organization_id':organization,'limit':200})['items'] if can('inventory.units.view') else []
        unit_names={u['id']:u.get('name') or u.get('code') or 'الوحدة الأساسية' for u in units}
        for item in items:
            item['base_unit_name']=unit_names.get(item.get('base_unit_id'),'الوحدة الأساسية')
        names={r['id']:r.get('name_ar') or r.get('code') for r in items}
        for row in balances+reservations: row['item_name']=names.get(row['item_id'],row['item_id'])
        if document:
            for line in document['lines']:
                item=next((item for item in items if item.get('id')==line.get('item_id')), {})
                line['item_name']=names.get(line['item_id'],line['item_id'])
                line['item_code']=item.get('code','')
                line['unit_name']=item.get('base_unit_name','الوحدة الأساسية')
                approved=Decimal(str(line.get('approved_quantity') or 0))
                fulfilled=Decimal(str(line.get('fulfilled_quantity') or 0))
                line['line_status']='مكتمل' if approved and fulfilled>=approved else ('قيد التنفيذ' if fulfilled else ('معتمد' if approved else 'بانتظار الاعتماد'))
        creator=document and document['created_by']==identity.get('id','').replace('-','')
        status=document['status'] if document else ''
        status_labels={'DRAFT':'مسودة','SUBMITTED':'بانتظار الاعتماد','APPROVED':'معتمد','PARTIAL':'قيد التنفيذ',
                       'FULFILLED':'مكتمل','CANCELLED':'ملغى','REJECTED':'مرفوض','CLOSED':'مغلق'}
        if document:
            document['status_label']=status_labels.get(status,status)
            completed=sum(1 for line in document.get('lines',[]) if line.get('line_status')=='مكتمل')
            document['completed_line_count']=completed
            document['remaining_line_count']=sum(1 for line in document.get('lines',[]) if Decimal(str(line.get('approved_quantity') or 0)) > Decimal(str(line.get('fulfilled_quantity') or 0)))
        progress_labels=[('DRAFT','مسودة'),('SUBMITTED','بانتظار الاعتماد'),('APPROVED','معتمد'),('PARTIAL','قيد التنفيذ'),('FULFILLED','مكتمل')]
        progress_rank={key:index for index,(key,_) in enumerate(progress_labels)}
        current_rank=progress_rank.get(status,-1)
        progress_steps=[{'key':key,'label':label,'state':'done' if index<current_rank else ('current' if index==current_rank else 'upcoming')}
                        for index,(key,label) in enumerate(progress_labels)]
        for row in records:
            row['status_label']=status_labels.get(row.get('status'),row.get('status','—'))
            row['line_count']=row.get('line_count',0)
        organization_name='الجهة الحالية'
        for context_item in work_context.get('items',[]):
            candidate=context_item.get('name') or context_item.get('label')
            if str(context_item.get('id','')).replace('-','')==str(organization).replace('-','') and candidate:
                try: UUID(str(candidate))
                except (ValueError,TypeError): organization_name=candidate
                break
        context={'page_title':'طلبات المواد','records':records,'document':document,
            'counts':listing.get('counts',{}),'total_records':listing.get('total',len(records)),
            'status_filter':status_filter,'search':search,'date_from':date_from,'date_to':date_to,
            'create_mode':request.GET.get('create')=='1' or bool(document and status=='DRAFT'),
            'status_labels':status_labels,
            'warehouses':warehouses,'selected_warehouse':selected,'reservations':reservations,'balances':balances,'locations':locations,
            'organization_name':organization_name,
            'items':items,'form_lines':posted_lines or (document['lines'] if document and status=='DRAFT' else [{}]),
            'error':error,'draft':request.POST,'reservation_key':request.POST.get('reservation_key') or uuid4().hex,
            'can_save':can('inventory.requests.create') and (not document or creator and status=='DRAFT'),
            'can_submit':can('inventory.requests.create') and creator and status=='DRAFT',
            'can_review':can('inventory.requests.approve') and document and not creator and status=='SUBMITTED',
            'can_cancel':can('inventory.requests.create') and creator and status in ('DRAFT','SUBMITTED','APPROVED','PARTIAL'),
            'can_close':can('inventory.requests.approve') and status in ('APPROVED','PARTIAL','FULFILLED'),
            'can_reserve':can('inventory.reservations.manage') and status in ('APPROVED','PARTIAL'),
            'can_manage_reservations':can('inventory.reservations.manage'),
            'progress_steps':progress_steps,
            'next_action':('مراجعة الطلب' if can('inventory.requests.approve') and status=='SUBMITTED' and document and not creator else
                           'تقديم الطلب للاعتماد' if can('inventory.requests.create') and creator and status=='DRAFT' else
                           'متابعة التنفيذ' if status in ('APPROVED','PARTIAL') else 'لا توجد إجراءات مطلوبة منك حالياً')}
        if document and not (request.GET.get('create')=='1' or status=='DRAFT'):
            return render(request,'inventory/request_detail.html',context)
        return render(request,'inventory/requests.html',context)
    except UnauthorizedException: return redirect('auth:login')
    except (ValueError,TypeError): return HttpResponse('تحقق من معرف الطلب ومعايير البحث',status=422)
    except ApiException as exc: return HttpResponse('تعذر تحميل طلبات المواد: '+str(exc),status=503)
