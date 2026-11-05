"""Settings definitions: ownership and override scope are independent."""
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from fastapi import HTTPException
from .settings_policy import validate_value

CATEGORIES = dict(overview='نظرة عامة', general='عام', institution='المؤسسة', security='الأمان والجلسات',
    appearance='المظهر والتخصيص', notifications='الإشعارات', modules='الوحدات والميزات',
    data='البيانات والنسخ الاحتياطي', audit='سجل التغييرات', advanced='متقدم')
ALL = ['system', 'institution', 'organization', 'user']
ORG = ALL[:-1]

def definition(key, label, category, default, kind='string', scopes=None, options=None, rules=None, description='', effect='بعد الحفظ'):
    permission = {'security': 'security', 'data': 'backup', 'advanced': 'advanced', 'modules': 'modules'}.get(category)
    return dict(key=key, label=label, category=category, default=default, kind=kind,
        scopes=scopes or ['system'], options=options or [], rules=rules or {}, description=description,
        permission=f'core.settings.{permission}.manage' if permission else 'core.settings.manage',
        sensitive=category in ('security', 'advanced', 'data'), owner='core', effect=effect)

DEFINITIONS = [
    definition('core.font_weight','سُمك الخط','appearance','400','select',ALL,
               ['400','500','600','700','800','900'],
               description='الأوزان المتاحة: 400 عادي، 500 متوسط، 600 شبه عريض، 700 عريض، 800 عريض جداً، 900 شديد السُمك.'),
    definition('core.logo','شعار المؤسسة','appearance','','image',description='PNG أو JPEG أو WebP؛ حتى 256 كيلوبايت و1024 بكسل.'),
    definition('core.system_name','اسم النظام','general','THE_SYSTEM',rules={'max_length':80}),
    definition('core.description','وصف النظام','general','النواة المؤسسية',rules={'max_length':250}),
    definition('core.language','اللغة المفضلة','general','ar','select',ALL,['ar','en'],description='واجهات النواة الحالية عربية؛ تحفظ اللغة المفضلة للوحدات الداعمة لها.'),
    definition('core.timezone','المنطقة الزمنية','general','Asia/Riyadh',scopes=ORG,description='التخزين يبقى UTC؛ تستخدم المنطقة عند تنسيق الوقت.'),
    definition('core.date_format','تنسيق التاريخ','general','Y-m-d','select',ALL,['Y-m-d','d/m/Y','m/d/Y']),
    definition('core.currency','العملة الافتراضية','general','SAR','select',ORG,['SAR','USD','EUR','AED','YER'],description='للوحدات المالية؛ لا تحول مبالغ قائمة.'),
    definition('core.decimals','المنازل العشرية','general',2,'integer',ORG,rules={'min':0,'max':6}),
    definition('core.institution.name','اسم المؤسسة','institution','المؤسسة',scopes=['system','institution']),
    definition('core.default_organization','الجهة الافتراضية للمؤسسة','institution','',scopes=['system','institution'],description='سياق عمل افتراضي؛ لا يغير العضوية أو الملكية أو الصلاحيات.'),
    definition('core.institution.code','رمز المؤسسة','institution','',scopes=['system','institution']),
    definition('core.institution.email','البريد الإلكتروني','institution','',scopes=['system','institution']),
    definition('core.institution.phone','الهاتف','institution','',scopes=['system','institution']),
    definition('core.institution.address','العنوان','institution','',scopes=['system','institution']),
    definition('core.institution.city','المدينة والدولة','institution','',scopes=['system','institution']),
    definition('core.theme','المظهر','appearance','light','select',ALL,['light','dark','system']),
    definition('core.font_size','حجم الخط','appearance',16,'integer',ALL,rules={'min':12,'max':24}),
    definition('core.density','كثافة العرض','appearance','comfortable','select',ALL,['comfortable','compact']),
    definition('core.primary_color','اللون الأساسي','appearance','#2766e9','select',options=['#2766e9','#146c60','#7044b3','#a64161']),
    definition('core.login_welcome','رسالة الترحيب','appearance','أهلاً بعودتك'),
    definition('core.security.password_length','الحد الأدنى لكلمة المرور','security',12,'integer',rules={'min':12,'max':64},effect='على كلمات المرور الجديدة فقط'),
    definition('core.security.password_complexity','اشتراط تنوع الأحرف','security',False,'boolean',effect='على كلمات المرور الجديدة فقط'),
    definition('core.security.login_attempts','محاولات الدخول قبل القفل','security',10,'integer',rules={'min':3,'max':30}),
    definition('core.security.lock_minutes','مدة القفل بالدقائق','security',15,'integer',rules={'min':1,'max':1440}),
    definition('core.security.session_minutes','مدة رمز الوصول بالدقائق','security',60,'integer',rules={'min':5,'max':1440},effect='على الجلسات الجديدة والمجددة'),
    definition('core.security.idle_minutes','الخروج بعد الخمول بالدقائق','security',10,'integer',rules={'min':5,'max':1440},effect='ينهي الجلسة بعد 10 دقائق بلا تواصل مع الخادم'),
    definition('core.security.refresh_days','مدة رمز التجديد بالأيام','security',7,'integer',rules={'min':1,'max':30},effect='على الرموز الجديدة'),
    definition('core.security.mfa_required','إلزام التحقق بخطوتين','security',False,'boolean',effect='يطبق على الدخول التالي؛ ينهي الجلسات بلا تحقق'),
    definition('core.security.alert_new_ip','تنبيه الدخول من عنوان جديد','security',True,'boolean',effect='إشعار داخل التطبيق عند تغير عنوان الدخول'),
    definition('core.security.multiple_sessions','السماح بجلسات متعددة','security',True,'boolean',effect='عند تعطيله ينهي الدخول التالي الجلسات السابقة'),
    definition('core.notifications.enabled','الإشعارات داخل التطبيق','notifications',True,'boolean'),
    definition('core.notifications.sound','تنبيه صوتي للإشعارات الجديدة','notifications',False,'boolean',ALL,description='يعمل بعد التفاعل مع الصفحة وسماح المتصفح بالصوت.'),
    definition('core.notifications.quiet','عدم الإزعاج','notifications',False,'boolean',ALL,description='يوقف التنبيه الصوتي؛ تبقى الإشعارات محفوظة ويمكن قراءتها.'),
    definition('core.notifications.retention_days','مدة الاحتفاظ بالأيام','notifications',90,'integer',rules={'min':7,'max':3650},effect='عند تشغيل تنظيف الإشعارات'),
    definition('core.backup.keep_count','عدد النسخ المحتفظ بها','data',10,'integer',rules={'min':2,'max':100},effect='عند إنشاء نسخة جديدة من المركز'),
    definition('core.maintenance','وضع الصيانة','advanced',False,'boolean',effect='يمنع الوصول لغير المدير؛ يستطيع المدير إيقافه'),
    # UDE-03 personal appearance contract. These keys reuse Core settings
    # tables, scope/version checks, audit, and reset semantics.
    definition('core.ude.theme','UDE theme','appearance','light','select',ALL,['light','dark','system']),
    definition('core.ude.palette','UDE palette','appearance','navy','select',ALL,['navy','royal-blue','emerald','modern-purple','turquoise','burgundy']),
    definition('core.ude.custom_colors','UDE custom colors','appearance',{},'json',ALL),
    definition('core.ude.luminance_adjustment','UDE luminance adjustment','appearance',0.0,'decimal',ALL,rules={'min':-0.12,'max':0.12}),
    definition('core.ude.font_family','UDE font family','appearance','Tajawal','select',ALL,['Tajawal','Almarai','IBM Plex Sans Arabic']),
    definition('core.ude.font_scale','UDE font scale','appearance','md','select',ALL,['sm','md','lg','xl']),
    definition('core.ude.radius','استدارة الزوايا','appearance','balanced','select',ALL,['compact','balanced','rounded']),
    definition('core.ude.card_style','نمط البطاقة','appearance','soft','select',ALL,['flat','soft','raised'],
               description='يحدد سطح البطاقة المحايد؛ ويظل مستوى الظل قابلاً للضبط مستقلاً.'),
    definition('core.ude.card_border','حد البطاقة','appearance','1px','select',ALL,['none','1px','2px'],
               description='يتحكم في سُمك حد البطاقات المشتركة.'),
    definition('core.ude.card_shadow','ظل البطاقة','appearance','light','select',ALL,['none','light','medium'],
               description='يحدد مستوى ظل البطاقات المشتركة.'),
    definition('core.ude.card_interaction','إبراز البطاقة عند التفاعل','appearance','highlight','select',ALL,['none','highlight','lift'],
               description='يطبق إبرازاً هادئاً أو رفعاً بسيطاً على البطاقات التفاعلية فقط.'),
    definition('core.ude.density','UDE density','appearance','comfortable','select',ALL,['comfortable','compact']),
    definition('core.ude.contrast','UDE contrast','appearance','normal','select',ALL,['normal','high']),
    definition('core.ude.motion','UDE motion','appearance','normal','select',ALL,['normal','reduced']),
    definition('core.ude.sidebar','UDE sidebar state','appearance','expanded','select',ALL,['expanded','collapsed']),
]

def catalog():
    result = {item['key']: dict(item) for item in DEFINITIONS}
    from core.module_registry import registry
    for module in registry.modules.values():
        for key, raw in module.settings.items():
            if raw.get('is_secret') or raw.get('is_encrypted'):
                continue  # Secret values belong in a dedicated secret store, never generic forms.
            if key not in result:
                item = definition(key,raw.get('label',key),'modules',raw['default'],raw['type'],
                    options=raw.get('options'),rules=raw.get('rules'))
                item['owner'] = module.code
                result[key] = item
    return result

def validate(item, value):
    if item['kind']=='image':
        if not value: return ''
        import base64,io
        from PIL import Image,UnidentifiedImageError
        try:
            if not isinstance(value,str) or len(value)>350000: raise ValueError()
            prefix,payload=value.split(',',1)
            if prefix not in ('data:image/png;base64','data:image/jpeg;base64','data:image/webp;base64'): raise ValueError()
            decoded=base64.b64decode(payload,validate=True)
            if len(decoded)>262144: raise ValueError()
            with Image.open(io.BytesIO(decoded)) as image:
                if max(image.size)>1024 or min(image.size)<1: raise ValueError()
                image.load()
                clean=io.BytesIO(); image.convert('RGBA').save(clean,format='PNG')
            if len(clean.getvalue())>262144: raise ValueError()
            return 'data:image/png;base64,'+base64.b64encode(clean.getvalue()).decode()
        except (ValueError,OSError,UnidentifiedImageError): raise HTTPException(422,'صورة الشعار غير صالحة أو تتجاوز الحد المسموح')
    validate_value(item['kind'],value,item['options'],item['rules'])
    if item['key'] == 'core.ude.custom_colors':
        import re
        if not isinstance(value, dict) or set(value) - {'primary','secondary','accent','surface','text'}:
            raise HTTPException(422,'UDE custom colors contain unknown keys')
        for color in value.values():
            if not isinstance(color, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
                raise HTTPException(422,'UDE custom color must be a six-digit hexadecimal color')
        if 'text' in value and 'surface' in value:
            def channel(part):
                n=int(part,16)/255
                return n/12.92 if n <= .04045 else ((n+.055)/1.055)**2.4
            def luminance(color):
                return .2126*channel(color[1:3])+ .7152*channel(color[3:5])+ .0722*channel(color[5:7])
            lo,hi=sorted((luminance(value['text']),luminance(value['surface'])))
            if (hi+.05)/(lo+.05) < 4.5:
                raise HTTPException(422,'UDE custom colors do not meet the 4.5:1 text contrast target')
    if isinstance(value,str) and len(value)>item['rules'].get('max_length',2000):
        raise HTTPException(422,'القيمة أطول من الحد المسموح')
    if item['key']=='core.timezone':
        try: ZoneInfo(value)
        except (ZoneInfoNotFoundError,ValueError): raise HTTPException(422,'منطقة زمنية غير معروفة')
    if item['key'].endswith('.email') and value:
        import re
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',value): raise HTTPException(422,'البريد الإلكتروني غير صحيح')
    return value
