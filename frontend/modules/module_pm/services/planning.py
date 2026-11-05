"""Presentation metadata; all commands are validated by the PM backend."""
KINDS = {
 'projects': ('المشاريع', 'project_code', None, [
     ('client_name','اسم العميل (اختياري)','text'),
     ('project_code','رمز المشروع','text'),('name','اسم المشروع','text'),
     ('organization_id','المنظمة','organizations'),('project_manager_user_id','مدير المشروع','managers'),
     ('currency','العملة','currencies'),('directive_date','تاريخ التوجيه','date'),('start_date','تاريخ البداية','date'),('daily_hours','ساعات العمل اليومية','number')]),
 'phases': ('المراحل','phase_code','projects', [('phase_code','رمز المرحلة','text'),('name','اسم المرحلة','text'),('owner_user_id','مسؤول المرحلة','owners')]),
 'tasks': ('المهام','task_code','phases', [('task_code','رمز المهمة','text'),('name','اسم المهمة','text'),('owner_user_id','مسؤول المهمة','owners')]),
 'activities': ('الأنشطة','activity_code','tasks', [('activity_code','رمز النشاط','text'),('name','اسم النشاط','text'),
     ('priority','الأولوية','priorities'),
     ('planned_quantity','الكمية المخططة','number'),('planned_duration','المدة المخططة','number'),('unit','الوحدة','text'),
     ('currency','عملة النشاط','currencies'),('rate_date','تاريخ سعر الصرف','date'),
     ('description','الوصف التفصيلي','textarea'),('notes','ملاحظات','textarea'),('attachment_url','رابط المرفق','url'),
     ('planned_start_date','البداية المخططة','date'),('planned_end_date','النهاية المخططة','date')]),
 'requirements': ('احتياجات الموارد','requirement_code','activities', [('requirement_code','رمز الاحتياج','text'),('name','اسم الاحتياج','text'),
     ('resource_type','نوع المورد','resource_types'),('item_category','تصنيف الاحتياج','item_categories'),
     ('specifications','وصف الاحتياج والمواصفات','textarea'),('unit','وحدة القياس','text'),
     ('quantity','الكمية المطلوبة','number'),('unit_price','سعر الوحدة','number'),('currency','عملة السعر','currencies'),('rate_date','تاريخ سعر الصرف','date'),
     ('productivity','معدل الإنتاجية','number'),('source','مصدر الاحتياج','text'),('notes','ملاحظات إضافية','textarea')]),
}
for _kind in ('phases', 'tasks', 'activities', 'requirements'):
    _label, _code, _parent, _fields = KINDS[_kind]
    KINDS[_kind] = (_label, _code, _parent, [field for field in _fields if field[0] != _code])

OPTIONAL = {'client_name','unit','resource_type','specifications','owner_user_id','description','notes','attachment_url',
            'planned_start_date','planned_end_date','source','item_category','productivity'}
PARENT_KEYS = {'tasks':'phase_id','activities':'task_id','requirements':'activity_id'}
NEXT = {'projects':'phases','phases':'tasks','tasks':'activities','activities':'requirements'}


def api_path(kind, project_id=None, entity_id=None):
    base = '/pm/projects' if kind == 'projects' else f'/pm/projects/{project_id}/{kind}'
    return base + ('/' + str(entity_id) if entity_id else '')


def allowed(identity, code):
    return identity.get('is_admin', False) or code in identity.get('permissions', [])
