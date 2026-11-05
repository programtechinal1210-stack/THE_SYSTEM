"""Display metadata and Django forms for existing PM commands."""
from datetime import date, datetime
import re
from django import forms

SECTIONS = {
    'baselines': ('اعتماد الخطة', 'pm.planning.view', 'pm.projects.update'),
    'dependencies': ('ترابط الأنشطة', 'pm.planning.view', 'pm.planning.manage'),
    'risks': ('المخاطر', 'pm.risks.view', 'pm.risks.manage'),
    'deviations': ('الانحرافات', 'pm.planning.view', 'pm.planning.manage'),
    'cashflows': ('التدفقات النقدية', 'pm.planning.view', 'pm.planning.manage'),
    'communications': ('خطة التواصل', 'pm.planning.view', 'pm.planning.manage'),
    'reports': ('التقارير اليومية', 'pm.reports.view', 'pm.planning.manage'),
    'weekly-plans': ('الخطط الأسبوعية', 'pm.wep.view', 'pm.wep.manage'),
    'work-orders': ('أوامر التشغيل', 'pm.execution.view', 'pm.execution.manage'),
}
CONTROL = {'risks', 'deviations', 'cashflows', 'communications', 'reports'}
WEP_NEXT = {'draft':['review','cancelled'], 'review':['approved','draft','cancelled'],
            'approved':['in_progress','reopened'], 'in_progress':['reopened'],
            'closed':['reopened'], 'reopened':['review','cancelled'], 'cancelled':[]}
# Action copy is intentionally distinct from the persisted lifecycle status.
WEP_ACTION_LABELS = {
    'review': 'إرسال للمراجعة',
    'approved': 'اعتماد الخطة',
    'in_progress': 'بدء متابعة الأسبوع',
    'closed': 'إغلاق الأسبوع',
    'reopened': 'إعادة فتح الأسبوع',
    'draft': 'إعادة إلى المسودة',
    'cancelled': 'إلغاء الخطة',
}
STATUS = {'draft':'مسودة', 'planning':'قيد التخطيط', 'review':'قيد المراجعة', 'approved':'معتمد', 'in_progress':'قيد التنفيذ',
          'reopened':'أعيد فتحه', 'closed':'مغلق', 'cancelled':'ملغى', 'issued':'صادر',
          'completed':'مكتمل', 'rejected':'مرفوض', 'active':'نشط', 'open':'مفتوح', 'submitted':'مقدم للاعتماد'}
WO_NEXT = {'issued':['in_progress'], 'in_progress':[], 'completed':[], 'closed':[], 'rejected':[]}


def text(label, required=False):
    return forms.CharField(label=label, required=required, max_length=2000)


def number(label, initial=0):
    return forms.DecimalField(label=label, min_value=0, max_digits=18, decimal_places=6, initial=initial)


def day(label, required=True):
    return forms.DateField(label=label, required=required, initial=date.today,
                           widget=forms.DateInput(attrs={'type':'date'}))


def moment(label, required=True, initial=None):
    return forms.DateTimeField(
        label=label,
        required=required,
        initial=initial,
        input_formats=['%Y-%m-%dT%H:%M', '%Y-%m-%dT%H:%M:%S'],
        widget=forms.DateTimeInput(
            format='%Y-%m-%dT%H:%M',
            attrs={'type': 'datetime-local', 'step': '60'},
        ),
    )


def choice(label, values, required=True):
    return forms.ChoiceField(label=label, required=required, choices=[('', 'اختر')] + list(values))


def next_risk_code(project_code, risks):
    """Suggest the next readable risk business key within this project."""
    project_code = re.sub(r'[^A-Za-z0-9_-]+', '-', str(project_code or 'PROJECT')).strip('-')
    prefix = f'R-{project_code}-'
    existing = {str(row.get('risk_code', '')).casefold() for row in risks}
    sequence = 1
    for row in risks:
        code = str(row.get('risk_code', ''))
        if code.casefold().startswith(prefix.casefold()):
            suffix = code[len(prefix):]
            if suffix.isdigit():
                sequence = max(sequence, int(suffix) + 1)
    candidate = f'{prefix}{sequence:03d}'
    while candidate.casefold() in existing:
        sequence += 1
        candidate = f'{prefix}{sequence:03d}'
    return candidate


def next_work_order_code(project_code, orders):
    """Suggest a readable work-order business key scoped to its project."""
    project_token = re.sub(r'[^A-Za-z0-9_-]+', '-', str(project_code or 'PROJECT')).strip('-') or 'PROJECT'
    prefix = f'WO-{project_token}-'
    existing = {str(row.get('work_order_code', '')).casefold() for row in orders}
    sequence = 1
    for row in orders:
        code = str(row.get('work_order_code', ''))
        if code.casefold().startswith(prefix.casefold()):
            suffix = code[len(prefix):]
            if suffix.isdigit():
                sequence = max(sequence, int(suffix) + 1)
    candidate = f'{prefix}{sequence:03d}'
    while candidate.casefold() in existing:
        sequence += 1
        candidate = f'{prefix}{sequence:03d}'
    return candidate


def next_consumption_code(work_order_code, consumptions):
    """Preview the server-assigned consumption key for one work order."""
    token = re.sub(r'[^A-Za-z0-9_-]+', '-', str(work_order_code or 'WORK-ORDER')).strip('-') or 'WORK-ORDER'
    prefix = f'CON-{token}-'
    codes = [str(row.get('consumption_code', '')) for row in consumptions]
    existing = {code.casefold() for code in codes}
    sequence = 1
    for code in codes:
        if code.casefold().startswith(prefix.casefold()):
            suffix = code[len(prefix):]
            if suffix.isdigit():
                sequence = max(sequence, int(suffix) + 1)
    candidate = f'{prefix}{sequence:03d}'
    while candidate.casefold() in existing:
        sequence += 1
        candidate = f'{prefix}{sequence:03d}'
    return candidate


def operation_form(kind, refs, data=None, initial=None, prefix=None):
    def ref(label, key, required=True):
        return choice(label, [(r['id'], r['name']) for r in refs[key]], required)
    def code(label='الرمز'):
        return forms.CharField(label=label, max_length=80)
    fields = {}
    if kind in ('risks', 'deviations'):
        fields = {('risk_code' if kind=='risks' else 'deviation_code'):code(),
                  'level':choice('مستوى الارتباط', [('project','المشروع'),('phase','المرحلة'),('task','المهمة'),('activity','النشاط')]),
                  'phase_id':ref('المرحلة', 'phases', False), 'task_id':ref('المهمة','tasks',False),
                  'activity_id':ref('النشاط','activities',False),
                  'description':forms.CharField(label='الوصف', max_length=2000, widget=forms.Textarea(attrs={'rows':3})),
                  'impact':forms.IntegerField(label='الأثر (1–5)', min_value=1,max_value=5,initial=1),
                  'corrective_action':text('الإجراء التصحيحي')}
        if kind=='risks':
            fields.update(classification=choice('التصنيف', [
                              ('منخفض', 'منخفض'), ('متوسط', 'متوسط'),
                              ('عالي', 'عالي'), ('حرج', 'حرج'),
                          ]), owner_user_id=ref('المسؤول','users',False),
                          probability=forms.DecimalField(label='الاحتمال (%)', min_value=0, max_value=100,
                                                         max_digits=18, decimal_places=6, initial=0),
                          discovery_date=day('تاريخ الاكتشاف',False))
        else:
            fields.update(deviation_type=text('نوع الانحراف'), causes=text('الأسباب'),
                          responsible_user_id=ref('المسؤول','users',False), target_date=day('التاريخ المستهدف',False))
    elif kind=='cashflows':
        fields = {'item_code':code(), 'cash_flow_type':choice('النوع',[('inflow','وارد'),('outflow','صادر')]),
                  'amount':number('المبلغ'), 'currency':ref('عملة المبلغ','currencies'), 'period':text('الفترة',True),
                  'rate_date':day('تاريخ سعر الصرف'), 'notes':text('ملاحظات')}
    elif kind=='communications':
        fields = {'item_code':code(), 'report_type':text('نوع التقرير'), 'purpose':text('الغرض'),
                  'frequency':text('التكرار'), 'sender_user_id':ref('المرسل','users',False),
                  'receivers':text('المستلمون'), 'mechanism':text('وسيلة التواصل'), 'notes':text('ملاحظات')}
    elif kind=='reports':
        fields = {'report_code':code(), 'report_date':day('تاريخ التقرير'),
                  'activities_count':forms.IntegerField(label='عدد الأنشطة',min_value=0,initial=0),
                  'planned_volume':number('الحجم المخطط'), 'executed_volume':number('الحجم المذكور في التقرير'),
                  'daily_cost':number('التكلفة المذكورة في التقرير'),
                  'actual_workers':forms.IntegerField(label='عدد العاملين',min_value=0,initial=0),
                  'work_hours':number('ساعات العمل'), 'equipment_used':text('المعدات'),
                  'materials_used':text('المواد'), 'problems':text('المشكلات'), 'notes':text('ملاحظات')}
    elif kind=='work-orders':
        fields = {
            'work_order_code': forms.CharField(
                label='رمز أمر التشغيل',
                required=False,
                max_length=80,
                help_text='يُنشأ رمز الأمر تلقائيًا حسب المشروع والتسلسل.',
                widget=forms.TextInput(attrs={
                    'autocomplete': 'off', 'placeholder': 'يُنشأ تلقائيًا',
                    'readonly': 'readonly', 'aria-readonly': 'true',
                }),
            ),
            'activity_id': ref('النشاط', 'activities'),
            'assignee_user_id': ref('المكلف', 'users', False),
            'issue_date': moment('تاريخ ووقت الإصدار', False, datetime.now),
            'planned_start_date': moment('تاريخ ووقت البداية المخطط له', False),
            'notes': forms.CharField(
                label='ملاحظات التنفيذ',
                required=False,
                max_length=2000,
                help_text='ملاحظات مرتبطة بهذا الأمر فقط.',
                widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'أضف تفاصيل موجزة عند الحاجة'}),
            ),
        }
        fields['activity_id'].help_text = 'اختر نشاطًا من خطة هذا المشروع.'
        fields['assignee_user_id'].help_text = 'اختياري؛ يمكن إسناد الأمر لاحقًا.'
        fields['issue_date'].help_text = 'يُستخدم تاريخ ووقت الإصدار الحاليان تلقائيًا عند تركه فارغًا.'
        fields['planned_start_date'].help_text = 'الموعد المستهدف لبدء تنفيذ النشاط؛ لا يمثل تاريخ بدء فعلي.'
    elif kind=='consumption':
        fields = {
            'consumption_code': forms.CharField(
                label='رمز سجل الاستهلاك',
                required=False,
                max_length=80,
                help_text='يُنشأ تلقائيًا عند حفظ سجل الاستهلاك.',
                widget=forms.TextInput(attrs={
                    'autocomplete': 'off', 'readonly': 'readonly', 'aria-readonly': 'true',
                }),
            ),
            'item_name': forms.CharField(
                label='اسم المورد أو المادة',
                required=True,
                max_length=2000,
                help_text='أدخل اسم المادة أو المورد المستهلك فعليًا.',
            ),
            'item_type': text('نوع المورد'),
            'quantity': forms.DecimalField(
                label='الكمية المستهلكة',
                min_value=0,
                max_digits=18,
                decimal_places=6,
                initial=0,
                help_text='أدخل كمية هذا السجل، لا إجمالي كميات أمر التشغيل.',
                widget=forms.NumberInput(attrs={'inputmode': 'decimal', 'step': 'any'}),
            ),
            'unit': forms.CharField(
                label='وحدة القياس',
                required=False,
                max_length=2000,
                help_text='مثال: كيس، متر، أو ساعة.',
            ),
            'unit_price': forms.DecimalField(
                label='سعر الوحدة',
                min_value=0,
                max_digits=18,
                decimal_places=6,
                initial=0,
                help_text='السعر بعملة المورد المختارة.',
                widget=forms.NumberInput(attrs={'inputmode': 'decimal', 'step': 'any'}),
            ),
            'currency': ref('عملة المورد', 'currencies'),
            'rate_date': day('تاريخ سعر الصرف'),
            'reference': text('المرجع'),
        }
        fields['currency'].help_text = 'تُحوّل التكلفة وفق سعر الصرف المثبت لهذا التاريخ.'
        fields['rate_date'].help_text = 'تاريخ تثبيت سعر الصرف المستخدم في حساب التكلفة.'
    elif kind=='quantity':
        fields = {'quantity': forms.DecimalField(
            label='كمية الإنجاز الجديدة',
            min_value=0.000001,
            max_digits=18,
            decimal_places=6,
            initial=0,
                help_text='أدخل كمية هذه الدفعة؛ سيضيفها النظام إلى الإجمالي السابق تلقائيًا.',
            widget=forms.NumberInput(attrs={'inputmode': 'decimal', 'step': 'any'}),
        ), 'notes': forms.CharField(label='ملاحظات الإنجاز', required=False, max_length=2000,
                                    widget=forms.Textarea(attrs={'rows': 2}))}
    elif kind=='update-order':
        fields = {'assignee_user_id': ref('المكلّف بالتنفيذ', 'users', False),
                  'issue_date': moment('تاريخ ووقت إصدار الأمر', False),
                  'planned_start_date': moment('تاريخ ووقت البداية المخطط له', False),
                  'notes': forms.CharField(label='ملاحظات الأمر', required=False, max_length=2000,
                                           widget=forms.Textarea(attrs={'rows': 3}))}
    elif kind in ('reject', 'partial-close'):
        label = 'سبب الرفض' if kind == 'reject' else 'سبب الإغلاق الجزئي'
        fields = {'reason': forms.CharField(label=label, required=True, min_length=3, max_length=2000,
                                            strip=True, widget=forms.Textarea(attrs={'rows': 3}))}
    elif kind=='weekly-plans':
        fields = {'week_code':code('رمز الأسبوع'), 'start_date':day('بداية الأسبوع'),
                  'end_date':day('نهاية الأسبوع')}
    elif kind=='item':
        fields = {'activity_id':ref('النشاط','activities'), 'weekly_target':number('الالتزام الأسبوعي'),
                  'assignee_user_id':ref('المكلف','users',False)}
    elif kind=='update-item':
        fields = {'weekly_target':number('الالتزام الأسبوعي'),
                  'assignee_user_id':ref('المكلف','users',False)}
    elif kind=='carryover':
        fields = {'next_week_code':code('رمز الأسبوع التالي'), 'next_start_date':day('بداية الأسبوع التالي'),
                  'next_end_date':day('نهاية الأسبوع التالي')}
    elif kind=='dependencies':
        fields = {'predecessor_id':ref('النشاط السابق','activities'), 'successor_id':ref('النشاط اللاحق','activities'),
                  'dependency_type':choice('نوع العلاقة', [('finish_to_start','نهاية إلى بداية'),('start_to_start','بداية إلى بداية'),
                                                         ('finish_to_finish','نهاية إلى نهاية'),('start_to_finish','بداية إلى نهاية')])}
    defaults = {'level':'project', 'cash_flow_type':'outflow', 'currency':refs['project']['currency'], 'dependency_type':'finish_to_start'}
    defaults.update(initial or {})
    planned_start = defaults.get('planned_start_date')
    if isinstance(planned_start, str) and len(planned_start) == 10:
        defaults['planned_start_date'] = f'{planned_start}T00:00'
    elif isinstance(planned_start, date) and not isinstance(planned_start, datetime):
        defaults['planned_start_date'] = datetime.combine(planned_start, datetime.min.time())
    form = forms.Form(data=data, initial=defaults, prefix=prefix)
    form.fields = fields
    return form


def payload(form):
    result = {}
    for key, value in form.cleaned_data.items():
        if key.endswith('_id') and not value:
            value = None
        elif value is not None and not isinstance(value, (str,int,bool)):
            value = value.isoformat() if hasattr(value,'isoformat') else str(value)
        result[key] = value
    if 'work_order_code' in form.fields and not result.get('work_order_code'):
        # Empty means "let the PM API assign the authoritative work-order key".
        result.pop('work_order_code', None)
    return result

