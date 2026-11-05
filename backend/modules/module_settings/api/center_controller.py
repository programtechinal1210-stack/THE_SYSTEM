from fastapi import APIRouter, Request, Depends, Query, HTTPException
from pydantic import BaseModel, Field
from datetime import date, timedelta
from sqlalchemy import text
from infrastructure.database.db_context import get_session
from core.access import allowed, require
from ..application.center_catalog import CATEGORIES
from ..application.center_service import scope_access, state, save

router=APIRouter(prefix='/api/v1/settings-center',tags=['settings-center'])

@router.get('/branding')
async def branding(session=Depends(get_session,scope='function')):
    from ..application.center_service import system_value
    return {key.removeprefix('core.'):await system_value(session,key) for key in
        ('core.system_name','core.description','core.logo','core.primary_color','core.login_welcome')}

class Change(BaseModel):
    key:str
    value:object=None
    reset:bool=False
    lock_user_override:bool|None=None

class Batch(BaseModel):
    scope:str='system'
    scope_id:str=''
    expected:str
    changes:list[Change]=Field(min_length=1,max_length=100)
    confirmed:bool=False
    reason:str=Field(default='',max_length=500)

@router.get('')
async def center(request:Request,scope:str='system',scope_id:str='',session=Depends(get_session,scope='function')):
    sid=await scope_access(session,request,scope,scope_id)
    rows,token=await state(session,scope,sid,request.state.user.organization_id)
    for row in rows:
        row['editable']=not row['locked'] and (scope=='user' or allowed(request,row['permission']))
        if scope!='user' and not request.state.is_admin:
            grants=request.state.permission_scopes.get(row['permission'],set())
            row['editable']=row['editable'] and ('institution' in grants if scope in ('system','institution') else bool(grants.intersection({'institution','organization'})))
        if row['category']=='advanced': row['editable']=request.state.is_admin
    rows=[r for r in rows if r['category']!='advanced' or request.state.is_admin]
    units=[]
    if scope!='user':
        query='SELECT id,name FROM organizations'
        if not request.state.is_admin: query+=' WHERE id=:id'
        units=[dict(r) for r in (await session.execute(text(query),{'id':request.state.user.organization_id.hex})).mappings()]
    return {'items':rows,'token':token,'scope':scope,'scope_id':sid,'categories':CATEGORIES,'units':units}

@router.post('/batch')
async def batch(data:Batch,request:Request,session=Depends(get_session,scope='function')):
    return await save(session,request,data.scope,data.scope_id,data.expected,data.changes,data.confirmed,data.reason)

@router.get('/changes')
async def changes(request:Request,search:str='',scope:str='',outcome:str='success',date_from:date|None=None,date_to:date|None=None,skip:int=Query(0,ge=0),session=Depends(get_session,scope='function')):
    require(request,'core.settings.audit.view')
    if outcome not in ('success','failed'): raise HTTPException(422,'حالة غير معروفة')
    if outcome=='failed':
        import json
        clauses=["a.module='settings-center'","a.status_code>=400","(a.changes_summary LIKE :q OR u.full_name LIKE :q)"]
        args={'q':'%'+search+'%','skip':skip}
        if not request.state.is_admin:
            clauses.append('a.user_id=:uid'); args['uid']=request.state.user.id.hex
        if date_from: clauses.append('a.created_at>=:start');args['start']=date_from.isoformat()
        if date_to: clauses.append('a.created_at<:end');args['end']=(date_to+timedelta(days=1)).isoformat()
        where=' AND '.join(clauses)
        sql=' FROM audit_logs a LEFT JOIN users u ON u.id=a.user_id WHERE '+where
        rows=(await session.execute(text('SELECT a.id,a.changes_summary,a.created_at,a.metadata,a.status_code,u.full_name'+sql+' ORDER BY a.id DESC LIMIT 50 OFFSET :skip'),args)).mappings()
        items=[dict(id=r['id'],setting_key=r['changes_summary'],scope_type='request',old_value='—',new_value='لم يطبق',actor_name=r['full_name'],created_at=r['created_at'],reason='طلب مرفوض: '+str(r['status_code']),request_id=json.loads(r['metadata'] or '{}').get('request_id'),batch_id='—') for r in rows]
        return {'items':items,'total':await session.scalar(text('SELECT count(*)'+sql),args)}
    clauses=['(setting_key LIKE :q OR actor_name LIKE :q)']; args={'q':'%'+search+'%','skip':skip}
    if scope: clauses.append('scope_type=:s'); args['s']=scope
    if date_from: clauses.append('created_at>=:start');args['start']=date_from.isoformat()
    if date_to: clauses.append('created_at<:end');args['end']=(date_to+timedelta(days=1)).isoformat()
    if not request.state.is_admin:
        clauses.append("(scope_type='user' AND scope_id=:uid OR scope_type='organization' AND scope_id=:oid)")
        args.update(uid=request.state.user.id.hex,oid=request.state.user.organization_id.hex)
    where=' AND '.join(clauses)
    rows=await session.execute(text('SELECT * FROM settings_changes WHERE '+where+' ORDER BY id DESC LIMIT 50 OFFSET :skip'),args)
    return {'items':[dict(r) for r in rows.mappings()],'total':await session.scalar(text('SELECT count(*) FROM settings_changes WHERE '+where),args)}

@router.get('/operations')
async def operations(request:Request,session=Depends(get_session,scope='function')):
    require(request,'core.settings.backup.manage')
    from ..application.center_operations import backups
    import asyncio
    return {'backups':await asyncio.to_thread(backups),'jobs':[dict(r) for r in (await session.execute(text('SELECT * FROM settings_operations ORDER BY created_at DESC LIMIT 30'))).mappings()]}

class Operation(BaseModel):
    action:str
    confirmed:bool=False

@router.post('/operations')
async def operate(data:Operation,request:Request,session=Depends(get_session,scope='function')):
    from ..application.center_operations import snapshot,inspect_database
    from ..application.center_service import system_value
    import asyncio,json
    from uuid import uuid4
    from datetime import datetime,timedelta
    permission='core.settings.manage' if data.action=='clean_notifications' else 'core.settings.backup.manage'
    require(request,permission)
    if not request.state.is_admin and 'institution' not in request.state.permission_scopes.get(permission,set()):
        raise HTTPException(403,'هذه العملية تتطلب صلاحية على مستوى المؤسسة')
    if not data.confirmed: raise HTTPException(422,'يجب تأكيد العملية')
    if data.action not in ('backup','integrity','clean_notifications'): raise HTTPException(422,'عملية غير معروفة')
    oid=uuid4().hex
    await session.execute(text("INSERT INTO settings_operations(id,kind,status,summary,actor_id) VALUES(:id,:kind,'running',:kind,:actor)"),{'id':oid,'kind':data.action,'actor':request.state.user.id.hex})
    await session.commit()
    try:
        if data.action=='backup': result=await asyncio.to_thread(snapshot,await system_value(session,'core.backup.keep_count'))
        elif data.action=='integrity': result=await asyncio.to_thread(inspect_database)
        else:
            cutoff=datetime.utcnow()-timedelta(days=await system_value(session,'core.notifications.retention_days'))
            deleted=await session.execute(text('DELETE FROM notifications WHERE created_at<:date'),{'date':cutoff})
            result={'removed':deleted.rowcount}
    except (OSError,ValueError) as exc:
        await session.rollback()
        await session.execute(text("UPDATE settings_operations SET status='failed',completed_at=CURRENT_TIMESTAMP,result=:result WHERE id=:id"),{'id':oid,'result':json.dumps({'error':'تعذر إكمال العملية؛ تحقق من التخزين وسلامة قاعدة البيانات'})})
        await session.commit()
        raise HTTPException(503,'فشلت العملية؛ راجع سجل العمليات') from exc
    await session.execute(text("UPDATE settings_operations SET status='completed',completed_at=CURRENT_TIMESTAMP,result=:result WHERE id=:id"),{'id':oid,'result':json.dumps(result,ensure_ascii=False)})
    request.state.audit_details={'entity_type':'settings.operation','entity_id':oid,'new':result}
    return {'id':oid,'result':result}

class Restore(BaseModel):
    backup_id:str=Field(max_length=80)
    confirmation:str=Field(max_length=20)
    current_password:str=Field(min_length=1,max_length=200)

@router.post('/restore')
async def restore_backup(data:Restore,request:Request):
    require(request,'core.settings.backup.manage')
    if not request.state.is_admin or data.confirmation!='RESTORE': raise HTTPException(403,'تتطلب الاستعادة مدير النظام وكتابة RESTORE')
    from infrastructure.authentication.password_hasher import PasswordHasher
    if not PasswordHasher().verify(data.current_password,request.state.user.password_hash): raise HTTPException(403,'كلمة المرور غير صحيحة')
    import asyncio
    from ..application.center_operations import restore
    from infrastructure.database.db_context import async_engine,sync_engine
    await async_engine.dispose(); sync_engine.dispose()
    try: result=await asyncio.to_thread(restore,data.backup_id,request.state.user.id.hex,request.state.user.full_name,getattr(request.state,'request_id',None))
    except ValueError as exc: raise HTTPException(422,str(exc))
    return {'result':result,'detail':'تمت الاستعادة وإنهاء الجلسات؛ سجّل الدخول مجددًا'}

@router.get('/modules')
async def modules(request:Request,session=Depends(get_session,scope='function')):
    require(request,'core.settings.view')
    from core.module_registry import registry
    from ..application.module_policy import enabled_modules
    effective=await enabled_modules(session)
    return [{'code':m.code,'name':m.name,'version':m.version,'enabled':effective[m.code],'dependencies':m.dependencies,
             'settings':list(m.settings),'protected':m.code in ('users','organizations','entities','settings','notifications','audit'),
             'health':'registered','href':m.href} for m in registry.modules.values()]

class ModuleChange(BaseModel):
    code:str
    enabled:bool
    confirmed:bool

@router.post('/modules')
async def toggle_module(data:ModuleChange,request:Request,session=Depends(get_session,scope='function')):
    from ..application.module_policy import PROTECTED,enabled_modules
    from core.module_registry import registry
    from ..infrastructure.models.system_setting_model import SystemSettingModel
    from sqlalchemy import select
    require(request,'core.settings.modules.manage')
    if not request.state.is_admin and 'institution' not in request.state.permission_scopes.get('core.settings.modules.manage',set()): raise HTTPException(403,'إدارة الوحدات تتطلب نطاق المؤسسة')
    module=registry.modules.get(data.code)
    if not module or not module.enabled: raise HTTPException(409,'الوحدة غير مثبتة للتشغيل')
    if data.code in PROTECTED: raise HTTPException(403,'لا يمكن تعطيل وحدات النواة الأساسية')
    if not data.confirmed: raise HTTPException(422,'راجع أثر تغيير حالة الوحدة')
    await session.execute(text("INSERT OR IGNORE INTO settings_scope_versions(scope_type,scope_id) VALUES('modules','')"))
    await session.execute(text("UPDATE settings_scope_versions SET version=version+1 WHERE scope_type='modules'"))
    enabled=await enabled_modules(session)
    if data.enabled and any(not enabled.get(dep) for dep in module.dependencies): raise HTTPException(409,'فعّل التبعيات أولًا')
    if not data.enabled and any(enabled[m.code] and data.code in m.dependencies for m in registry.modules.values()): raise HTTPException(409,'توجد وحدات مفعلة تعتمد على هذه الوحدة')
    key='core.module_enabled.'+data.code
    row=await session.scalar(select(SystemSettingModel).where(SystemSettingModel.key==key))
    if row: row.value=data.enabled
    else: session.add(SystemSettingModel(key=key,value=data.enabled,default_value=True,data_type='boolean',is_active=True,is_encrypted=False))
    request.state.audit_details={'old':{'enabled':enabled[data.code]},'new':{'enabled':data.enabled},'summary':'Module state: '+data.code}
    return {'code':data.code,'enabled':data.enabled}

@router.get('/sessions')
async def sessions(request:Request,session=Depends(get_session,scope='function')):
    require(request,'core.settings.security.manage')
    # Institution-wide session administration is reserved for the system administrator.
    clause='' if request.state.is_admin else ' AND s.user_id=:uid'
    return [dict(r) for r in (await session.execute(text('SELECT s.id,u.full_name,s.ip_address,s.login_time,s.expiry_time FROM user_sessions s JOIN users u ON u.id=s.user_id WHERE s.is_active=1 AND s.expiry_time>CURRENT_TIMESTAMP'+clause),{'uid':request.state.user.id.hex})).mappings()]

@router.delete('/sessions/{sid}')
async def end_session(sid:str,request:Request,session=Depends(get_session,scope='function')):
    from uuid import UUID
    require(request,'core.settings.security.manage')
    try: sid=UUID(sid).hex
    except ValueError: raise HTTPException(422,'جلسة غير صالحة')
    clause='' if request.state.is_admin else ' AND user_id=:uid'
    result=await session.execute(text('UPDATE user_sessions SET is_active=0,logout_time=CURRENT_TIMESTAMP WHERE id=:sid'+clause),{'sid':sid,'uid':request.state.user.id.hex})
    if not result.rowcount: raise HTTPException(404,'الجلسة غير متاحة')
    return {'detail':'تم إنهاء الجلسة'}
