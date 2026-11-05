"""Atomic scoped settings with optimistic concurrency and a dedicated change history."""
import json
import hashlib
from uuid import UUID, uuid4
from sqlalchemy import text, select
from fastapi import HTTPException
from core.access import allowed, require
from .center_catalog import catalog, validate
from ..infrastructure.models.system_setting_model import SystemSettingModel

async def scope_access(session, request, scope, scope_id):
    if scope not in ('system','institution','organization','user'):
        raise HTTPException(422,'نطاق غير معروف')
    if scope in ('system','institution'):
        scope_id = ''
        require(request,'core.settings.view')
    elif scope == 'user':
        scope_id = request.state.user.id.hex
    else:
        try: scope_id = UUID(scope_id).hex
        except (ValueError,TypeError): raise HTTPException(422,'اختر الوحدة التنظيمية')
        require(request,'core.settings.view')
        if not request.state.is_admin and scope_id != request.state.user.organization_id.hex:
            raise HTTPException(403,'الوحدة خارج نطاقك')
        if not await session.scalar(text('SELECT 1 FROM organizations WHERE id=:id'),{'id':scope_id}):
            raise HTTPException(404,'الوحدة غير موجودة')
    return scope_id

async def state(session, scope='system', scope_id='', user_org=None, include_inherited=False):
    definitions = catalog()
    system = {row.key:row for row in (await session.scalars(select(SystemSettingModel))).all()}
    overrides = (await session.execute(text('SELECT * FROM setting_overrides'))).mappings().all()
    lookup = {(r['scope_type'],r['scope_id'],r['setting_key']):json.loads(r['value']) for r in overrides}
    chain = [('system','')]
    if scope != 'system': chain.append(('institution',''))
    org = scope_id if scope=='organization' else user_org
    if org and scope in ('organization','user'):
        org = str(org).replace('-','')
        ancestors, seen = [], set()
        while org and org not in seen:
            seen.add(org); ancestors.append(('organization',org))
            org = await session.scalar(text('SELECT parent_id FROM organizations WHERE id=:id'),{'id':org})
        chain += list(reversed(ancestors))
    if scope=='user': chain.append(('user',scope_id))
    personal = {}
    if scope=='user':
        rows = (await session.execute(text('SELECT setting_key,value FROM user_settings WHERE user_id=:id'),{'id':scope_id})).all()
        personal = {'core.'+key:json.loads(value) for key,value in rows}
    result = []
    for key,item in definitions.items():
        if scope not in item['scopes'] and not include_inherited: continue
        base = system.get(key)
        value = base.value if base and base.is_active and not base.is_encrypted else item['default']
        source = 'system' if base and base.is_active else 'default'
        locked = bool(base and (base.validation_rules or {}).get('user_override') is False)
        if scope=='user' and key in personal and not locked:
            lookup.setdefault(('user',scope_id,key),personal[key])
        own = False
        for level,sid in chain[1:]:
            if level not in item['scopes'] or (level=='user' and locked): continue
            if (level,sid,key) in lookup:
                value,source=lookup[(level,sid,key)],level
                if level==scope and sid==scope_id: own=True
        result.append({**item,'value':value,'source':source,'overridden':own,'locked':scope=='user' and locked,'user_override_allowed':not locked})
    # Include inherited values in the token: editing a parent invalidates a stale child form.
    versions={(r[0],r[1]):r[2] for r in (await session.execute(text('SELECT scope_type,scope_id,version FROM settings_scope_versions'))).all()}
    revision=[(level,sid,versions.get((level,sid),0)) for level,sid in chain]
    token = hashlib.sha256(json.dumps([result,revision],sort_keys=True,ensure_ascii=False,default=str).encode()).hexdigest()
    return result,token

async def save(session, request, scope, scope_id, expected, changes, confirmed=False, reason=''):
    scope_id=await scope_access(session,request,scope,scope_id)
    # Acquire SQLite's writer before checking the snapshot, preventing lost updates.
    await session.execute(text('INSERT OR IGNORE INTO settings_scope_versions(scope_type,scope_id) VALUES(:s,:i)'),{'s':scope,'i':scope_id})
    await session.execute(text('UPDATE settings_scope_versions SET version=version WHERE scope_type=:s AND scope_id=:i'),{'s':scope,'i':scope_id})
    rows,token=await state(session,scope,scope_id,request.state.user.organization_id)
    if token != expected: raise HTTPException(409,'تغيرت القيم منذ فتح الصفحة. أعد تحميلها وراجع تعديلاتك.')
    available={r['key']:r for r in rows}
    if len(changes)>100 or len({c.key for c in changes})!=len(changes): raise HTTPException(422,'قائمة تغييرات غير صالحة')
    pending=[]
    for change in changes:
        item=available.get(change.key)
        if not item or item['locked']: raise HTTPException(403,'الإعداد غير قابل للتعديل في هذا النطاق')
        if scope!='user':
            require(request,item['permission'])
            grants=request.state.permission_scopes.get(item['permission'],set())
            if not request.state.is_admin and (scope in ('system','institution') and 'institution' not in grants or scope=='organization' and not grants.intersection({'organization','institution'})):
                raise HTTPException(403,'صلاحية التعديل لا تغطي هذا النطاق')
        if item['category']=='advanced' and not request.state.is_admin: raise HTTPException(403,'للمدير الأعلى فقط')
        if item['sensitive'] and not confirmed: raise HTTPException(422,'راجع أثر التغييرات الحساسة قبل التأكيد')
        if not change.reset: change.value=validate(item,change.value)
        if change.lock_user_override is not None and (scope!='system' or 'user' not in item['scopes']):
            raise HTTPException(422,'قفل التفضيل الشخصي متاح في نطاق النظام فقط')
        if change.key == 'core.default_organization':
            from core.work_context import validate_default
            await validate_default(session, item['default'] if change.reset else change.value)
        pending.append((change,item))
    batch=uuid4().hex
    for change,item in pending:
        key=change.key
        if scope=='system':
            model=await session.scalar(select(SystemSettingModel).where(SystemSettingModel.key==key))
            new=item['default'] if change.reset else change.value
            if model is None:
                model=SystemSettingModel(key=key,value=new,default_value=item['default'],data_type='string' if item['kind']=='image' else item['kind'],is_active=True,is_encrypted=False)
                session.add(model)
            else: model.value=new; model.is_active=True
            model.updated_by=request.state.user.id
            if change.lock_user_override is not None:
                model.validation_rules={**(model.validation_rules or {}),'user_override':not change.lock_user_override}
        else:
            args={'k':key,'s':scope,'i':scope_id,'v':json.dumps(change.value,ensure_ascii=False),'u':request.state.user.id.hex}
            if change.reset:
                await session.execute(text('DELETE FROM setting_overrides WHERE setting_key=:k AND scope_type=:s AND scope_id=:i'),args)
            else:
                await session.execute(text('INSERT INTO setting_overrides(setting_key,scope_type,scope_id,value,updated_by) VALUES(:k,:s,:i,:v,:u) ON CONFLICT(setting_key,scope_type,scope_id) DO UPDATE SET value=excluded.value,updated_by=excluded.updated_by,updated_at=CURRENT_TIMESTAMP'),args)
            if scope=='user':
                # Remove the legacy preference so resetting actually restores inheritance.
                await session.execute(text('DELETE FROM user_settings WHERE user_id=:u AND setting_key=:k'),{'u':scope_id,'k':key.removeprefix('core.')})
            new=None if change.reset else change.value
        old_audit=item['value']; new_audit=new
        if item['kind']=='image': old_audit=bool(old_audit); new_audit=bool(new_audit)
        if change.lock_user_override is not None:
            old_audit={'value':old_audit,'user_override':item['user_override_allowed']}
            new_audit={'value':new_audit,'user_override':not change.lock_user_override}
        await session.execute(text('INSERT INTO settings_changes(batch_id,setting_key,scope_type,scope_id,old_value,new_value,actor_id,actor_name,request_id,reason) VALUES(:b,:k,:s,:i,:o,:n,:u,:a,:r,:reason)'),
            dict(b=batch,k=key,s=scope,i=scope_id,o=json.dumps(old_audit,ensure_ascii=False),n=json.dumps(new_audit,ensure_ascii=False),u=request.state.user.id.hex,a=request.state.user.full_name,r=getattr(request.state,'request_id',None),reason=reason))
    await session.execute(text('UPDATE settings_scope_versions SET version=version+1 WHERE scope_type=:s AND scope_id=:i'),{'s':scope,'i':scope_id})
    await session.flush()
    request.state.audit_details={'entity_type':'settings.batch','entity_id':batch,'new':{'keys':[c.key for c in changes],'scope':scope}}
    return {'batch_id':batch,'count':len(pending)}

async def system_value(session,key):
    value=await session.scalar(select(SystemSettingModel.value).where(SystemSettingModel.key==key,SystemSettingModel.is_active.is_(True),SystemSettingModel.is_encrypted.is_(False)))
    return catalog()[key]['default'] if value is None else value
