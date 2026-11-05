"""Django adapter for the settings center; FastAPI owns permissions and persistence."""
import json
from pathlib import Path
from urllib.parse import quote
from django.conf import settings as django_settings
from django.shortcuts import render,redirect
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from shared.services.api_client import ApiClient,ApiException,UnauthorizedException,ForbiddenException,ConflictException

LABELS=dict(overview='نظرة عامة',general='عام',institution='المؤسسة',security='الأمان والجلسات',appearance='المظهر والتخصيص',notifications='الإشعارات',modules='الوحدات والميزات',data='البيانات والنسخ الاحتياطي',audit='سجل التغييرات',advanced='متقدم')
SOURCES=dict(default='القيمة الأصلية',system='النظام',institution='المؤسسة',organization='الوحدة التنظيمية',user='تفضيلك الشخصي')
OPTIONS={'light':'فاتح','dark':'داكن','system':'حسب الجهاز','ar':'العربية','en':'الإنجليزية','comfortable':'مريح','compact':'مكثّف','balanced':'متوازن','rounded':'مستدير',
    'navy':'\u0627\u0644\u0643\u062d\u0644\u064a \u0627\u0644\u0645\u0624\u0633\u0633\u064a',
    'royal-blue':'\u0627\u0644\u0623\u0632\u0631\u0642 \u0627\u0644\u0645\u0644\u0643\u064a',
    'emerald':'\u0627\u0644\u0623\u062e\u0636\u0631 \u0627\u0644\u0632\u0645\u0631\u062f\u064a',
    'modern-purple':'\u0627\u0644\u0628\u0646\u0641\u0633\u062c\u064a \u0627\u0644\u0639\u0635\u0631\u064a',
    'turquoise':'\u0627\u0644\u0641\u064a\u0631\u0648\u0632\u064a',
    'burgundy':'\u0627\u0644\u0639\u0646\u0627\u0628\u064a',
    'flat':'مسطّح','soft':'ناعم','raised':'بارز',
    'none':'بدون','1px':'1 بكسل','2px':'2 بكسل',
    'light':'خفيف','medium':'متوسط','highlight':'إبراز هادئ','lift':'رفع بسيط'}

def _ude_palette_enabled(identity=None):
    try:
        flag_path = Path(django_settings.BASE_DIR) / 'shared' / 'static' / 'ude' / 'ude-color-palettes-v1.0-feature-flags.json'
        flag = json.loads(flag_path.read_text(encoding='utf-8'))
        if not (flag.get('default_enabled') is True and flag.get('production_load') is False and flag.get('settings_surface') is True):
            return False
        identity = identity or {}
        permissions = set(identity.get('permissions') or [])
        required_permission = str(flag.get('required_permission') or 'core.settings.view')
        if not (identity.get('is_admin') or required_permission in permissions):
            return False
        pilot_ids = {str(value) for value in flag.get('pilot_user_ids', [])}
        pilot_usernames = {str(value) for value in flag.get('pilot_usernames', [])}
        return str(identity.get('id', '')) in pilot_ids or str(identity.get('username', '')) in pilot_usernames
    except (OSError, ValueError, TypeError):
        return False

def page(request,category='overview'):
    client=ApiClient(); context={'section':'settings','page_title':'مركز الإعدادات','category':category}
    try:
        identity=client.get('/auth/me'); request.core_identity=identity
        request.core_modules=client.get('/modules')
        can=lambda code:identity.get('is_admin') or code in identity.get('permissions',[])
        scope=request.GET.get('scope','system' if can('core.settings.view') else 'user')
        result=client.get('/settings-center',{'scope':scope,'scope_id':request.GET.get('scope_id','')})
        query=request.GET.get('q','').strip()
        items=result['items']
        for item in items:
            item['source_label']=SOURCES.get(item['source'],item['source'])
            item['input_value']=json.dumps(item['value'],ensure_ascii=False) if item['kind']=='json' else str(item['value'])
            item['options_ui']=[{'value':str(v),'label':OPTIONS.get(str(v),str(v)),'selected':v==item['value']} for v in item['options']]
            item['category_label']=LABELS.get(item['category'],item['category'])
        available={i['category'] for i in items}
        if scope!='user':
            available.add('modules')
            if can('core.settings.audit.view'): available.add('audit')
            if can('core.settings.backup.manage'): available.add('data')
        else: available.add('notifications')
        available.add('overview')
        if category not in available and not query:
            return render(request,'core/settings_center.html',{**context,'error':'القسم غير متاح في النطاق الحالي.'},status=403)
        selected=[i for i in items if query.casefold() in ' '.join([i['label'],i['key'],i['description'],i['category_label']]).casefold()] if query else [i for i in items if i['category']==category]
        context.update(identity=identity,scope=scope,scope_id=result['scope_id'],scope_label=SOURCES[scope],snapshot=result['token'],items=selected,query=query,units=result['units'],can_system=can('core.settings.view'),category_title='نتائج البحث' if query else LABELS[category],navigation=[{'code':k,'name':v,'active':k==category} for k,v in LABELS.items() if k in available],can_save=any(i['editable'] for i in selected),is_personal=scope=='user',can_backup=can('core.settings.backup.manage'),ude_color_palettes_enabled=_ude_palette_enabled(identity))
        if scope!='user' and category in ('overview','audit') and can('core.settings.audit.view'):
            history_params={key:request.GET[key] for key in ('date_from','date_to','outcome') if request.GET.get(key)}
            history=client.get('/settings-center/changes',{**history_params,'search':request.GET.get('history_search',''),'scope':request.GET.get('history_scope',''),'skip':request.GET.get('skip',0)})
            for row in history['items']: row['scope_label']=SOURCES.get(row['scope_type'],row['scope_type'])
            context['history']=history['items'][:5] if category=='overview' else history['items']
            context['next_skip']=int(request.GET.get('skip',0))+50
            context['history_more']=context['next_skip']<history['total']
            next_query=request.GET.copy(); next_query['skip']=context['next_skip']; context['history_next_query']=next_query.urlencode()
        context['can_modules']=can('core.settings.modules.manage')
        if scope!='user' and category in ('overview','modules'): context['modules']=client.get('/settings-center/modules')
        if scope!='user' and category in ('overview','data') and can('core.settings.backup.manage'): context.update(client.get('/settings-center/operations'))
        if category=='security' and can('core.settings.security.manage'): context['sessions']=client.get('/settings-center/sessions')
        if category=='notifications' and scope=='user': context['notification_types']=client.get('/user-notification-settings/available')
    except UnauthorizedException:
        request.session.flush()
        messages.warning(request, "انتهت جلستك بسبب الخمول لمدة 10 دقائق أو إعادة تشغيل النظام؛ سجّل الدخول مجددًا")
        return redirect("auth:login")
    except ForbiddenException:
        return render(request,'core/settings_center.html',{**context,'error':'ليست لديك صلاحية هذا القسم أو النطاق.'},status=403)
    except (ApiException,ValueError,KeyError) as exc:
        return render(request,'core/settings_center.html',{**context,'error':str(exc)},status=400)
    return render(request,'core/settings_center.html',context)

@require_POST
def action(request):
    client=ApiClient(); client.timeout=120
    try:
        body=json.loads(request.body); operation=body.pop('operation','batch')
        if operation in ('batch','operations','restore','modules'): result=client.post('/settings-center/'+operation,body)
        elif operation=='revoke': result=client.delete('/settings-center/sessions/'+quote(body['id'],safe=''))
        elif operation=='notification': result=client.put('/user-notification-settings/by-type/'+quote(body['code'],safe=''),{'is_enabled':body['enabled']})
        else: return JsonResponse({'detail':'عملية غير معروفة'},status=400)
        if operation=='restore': request.session.flush()
        return JsonResponse(result)
    except UnauthorizedException: return JsonResponse({'detail':'انتهت الجلسة؛ سجّل الدخول مجددًا'},status=401)
    except ForbiddenException as exc: return JsonResponse({'detail':str(exc)},status=403)
    except ConflictException as exc: return JsonResponse({'detail':str(exc)},status=409)
    except (ApiException,ValueError,KeyError,TypeError) as exc: return JsonResponse({'detail':str(exc)},status=400)
