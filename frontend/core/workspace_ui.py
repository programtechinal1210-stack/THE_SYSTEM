"""Presentation mapping: row actions stay beside their records, not above them."""
def prepare(context):
    section = context['section']
    action_labels = {'CREATE': 'إضافة', 'UPDATE': 'تعديل', 'DELETE': 'إزالة',
        'LOGIN': 'تسجيل دخول', 'LOGOUT': 'تسجيل خروج', 'REFRESH': 'تجديد الجلسة',
        'EXPORT': 'تصدير', 'REQUEST_DENIED': 'عملية مرفوضة'}
    module_labels = {'users': 'المستخدمين', 'auth': 'الحساب', 'org-units': 'الهيكل التنظيمي',
        'roles': 'الأدوار', 'permissions': 'الصلاحيات', 'settings': 'الإعدادات',
        'user-settings': 'التفضيلات', 'notifications': 'الإشعارات', 'profile': 'الملف الشخصي',
        'audit': 'التدقيق', 'user-notification-settings': 'تفضيلات الإشعارات'}
    for activity in context.get('activity', []):
        raw = activity.get('description_ar') or ''
        parts = raw.split(' ')
        activity['display_summary'] = (action_labels[parts[0]] + ' · ' + module_labels[parts[1]]) if len(parts) == 2 and parts[0] in action_labels and parts[1] in module_labels else raw
        activity['display_verb'] = action_labels.get(activity.get('verb'), activity.get('verb'))
    forms = context.get('forms', [])
    setting_labels = {'core.system_name': 'اسم النظام', 'core.language': 'لغة النظام',
                      'core.theme': 'المظهر الافتراضي', 'core.font_size': 'حجم الخط الافتراضي'}
    personal = {item['setting_key']: item for item in context.get('personal', [])}
    context['preference_cards'] = [
        {'label': {'theme': 'المظهر', 'font_size': 'حجم الخط', 'language': 'اللغة'}.get(key, key),
         'value': {'light': 'فاتح', 'dark': 'داكن', 'system': 'حسب الجهاز', 'ar': 'العربية', 'en': 'الإنجليزية'}.get(str(item['value']), item['value']),
         'source': {'system': 'من المؤسسة', 'user': 'تفضيلك الشخصي', 'default': 'القيمة الافتراضية'}.get(item.get('source'), ''),
         'locked': item.get('locked', False)} for key, item in personal.items()]
    for form in forms:
        for key, label in setting_labels.items():
            form['title'] = form['title'].replace(key, label)
        form['title'] = form['title'].replace('core.user.created', 'إنشاء الحساب')
        fields = {field['name']: field for field in form['fields']}
        for field in form['fields']:
            for option in field.get('options') or []:
                option['label'] = setting_labels.get(option['label'], option['label'])
        if section == 'profile' and form['action'] == 'preference':
            key = (fields['key'].get('options') or [{}])[0].get('value')
            if key in personal:
                fields['value']['value'] = str(personal[key]['value'])
                form['locked'] = personal[key].get('locked', False)
        if section == 'settings' and form['action'] == 'save':
            kind = fields['data_type']['options'][0]['value']
            if kind == 'boolean':
                fields['value']['options'] = [{'value': 'true', 'label': 'مفعّل'}, {'value': 'false', 'label': 'متوقف'}]
            elif kind in ('integer', 'decimal'):
                fields['value']['type'] = 'number'
    edits = {}
    primary, secondary = [], []
    for index, form in enumerate(forms):
        form['dialog_id'] = f'core-form-{index}'
        if form['action'] in ('update', 'save'):
            selector = next((f for f in form['fields'] if f['name'] in ('id', 'key')), None)
            if selector and len(selector.get('options') or []) == 1:
                edits[str(selector['options'][0]['value'])] = form['dialog_id']
                continue
        (primary if form['action'] in ('create', 'create_entity') or (form['action'] == 'create_type' and not context.get('entity_types')) else secondary).append(form)
    context['primary_actions'], context['secondary_actions'] = primary, secondary
    context['records'] = []
    for index, cells in enumerate(context.get('rows', [])):
        item = context.get('items', [])[index] if index < len(context.get('items', [])) else {}
        if section == 'audit':
            cells = list(cells)
            cells[1] = action_labels.get(cells[1], cells[1])
            cells[2] = module_labels.get(cells[2], cells[2])
        elif section == 'settings':
            cells = list(cells)
            cells[0] = setting_labels.get(item.get('key'), cells[0])
            cells[2] = {'string': 'نص', 'integer': 'عدد صحيح', 'decimal': 'رقم',
                        'boolean': 'تشغيل / إيقاف', 'select': 'اختيار', 'json': 'بيانات منظمة'}.get(cells[2], cells[2])
        context['records'].append({'cells': cells, 'item': item,
            'fields': list(zip(context.get('headings', []), cells)),
            'edit': edits.get(str(item.get('key') or item.get('id', '')))})
    for node in context.get('tree_nodes', []):
        node['edit_dialog'] = edits.get(str(node['id']))
    context['page_description'] = {
        'home': 'نظرة على مساحة عملك وآخر المستجدات',
        'users': 'إدارة حسابات الفريق وأدوارهم والوصول إلى النظام',
        'roles': 'تنظيم الأدوار وتحديد الصلاحيات الممنوحة لكل دور',
        'units': 'هيكل مؤسستك، من الإدارات الرئيسية إلى الفرق',
        'entities': 'دليل موحّد للجهات وبيانات التواصل المرتبطة بها',
        'settings': 'إعدادات مشتركة وتجربة عمل تناسب مؤسستك',
        'notifications': 'كل ما يهمك من تحديثات في مكان واحد',
        'audit': 'سجل واضح للعمليات والتغييرات داخل النظام',
        'profile': 'بياناتك الشخصية وتفضيلاتك وأمان حسابك',
    }.get(section, '')
    return context
