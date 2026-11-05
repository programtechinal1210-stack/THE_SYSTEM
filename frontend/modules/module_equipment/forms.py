import json
from uuid import uuid4

from django import forms
from django.utils import timezone


class JsonObjectField(forms.CharField):
    def to_python(self, value):
        value = super().to_python(value)
        if not value:
            return {}
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise forms.ValidationError("أدخل JSON صالحاً.") from exc
        if not isinstance(parsed, dict):
            raise forms.ValidationError("يجب أن تكون القيمة كائن JSON.")
        if len(json.dumps(parsed, ensure_ascii=False)) > 16000:
            raise forms.ValidationError("حجم بيانات JSON يتجاوز الحد المسموح.")
        return parsed


class EquipmentForm(forms.Form):
    json_fields = ()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css_class = "form-select" if isinstance(field, forms.ChoiceField) else "form-control"
            field.widget.attrs.setdefault("class", css_class)

    def payload(self):
        values = dict(self.cleaned_data)
        for key in self.json_fields:
            values[key] = self.cleaned_data[key]
        for key, value in tuple(values.items()):
            if value is None:
                values.pop(key)
            elif hasattr(value, "isoformat"):
                values[key] = value.isoformat()
            elif key in {
                "meter_initial", "meter_reading", "acquisition_value",
                "interval_meter", "first_due_meter", "reading_value",
                "old_final_reading", "new_initial_reading", "corrected_reading",
                "quantity", "unit_cost",
            }:
                values[key] = str(value)
            elif key in {
                "category_id", "owner_entity_id", "responsible_entity_id", "currency_id",
                "parent_id", "requested_entity_id", "request_id", "assignment_id", "inspection_id",
                "related_issue_event_id",
                "inventory_item_id", "maintenance_order_id",
                "installation_inventory_document_id", "removal_inventory_document_id",
                "lifecycle_id",
            }:
                values[key] = str(value)
        return values


class CategoryForm(EquipmentForm):
    json_fields = ("spec_schema", "inspection_schema", "maintenance_rules")

    category_code = forms.CharField(label="رمز التصنيف", max_length=50)
    name_ar = forms.CharField(label="الاسم العربي", max_length=180)
    name_en = forms.CharField(label="الاسم الإنجليزي", max_length=180, required=False)
    parent_id = forms.UUIDField(label="التصنيف الأب", required=False)
    meter_type = forms.ChoiceField(
        label="نوع العداد",
        choices=(("hours", "ساعات"), ("distance", "مسافة"), ("cycles", "دورات"),
                 ("energy", "طاقة"), ("none", "دون عداد")),
    )
    meter_unit = forms.CharField(label="وحدة العداد", max_length=20)
    output_unit = forms.CharField(label="وحدة الإنتاج", max_length=180, required=False)
    fuel_unit = forms.CharField(label="وحدة الوقود", max_length=180, required=False)
    spec_schema = JsonObjectField(label="مخطط المواصفات JSON", required=False, initial="{}",
                                  widget=forms.Textarea(attrs={"rows": 3}))
    inspection_schema = JsonObjectField(label="مخطط الفحص JSON", required=False, initial="{}",
                                        widget=forms.Textarea(attrs={"rows": 3}))
    maintenance_rules = JsonObjectField(label="قواعد الصيانة JSON", required=False, initial="{}",
                                        widget=forms.Textarea(attrs={"rows": 3}))

    def clean(self):
        cleaned = super().clean()
        expected_unit = {
            "hours": "h",
            "distance": "km",
            "cycles": "cycle",
            "energy": "kWh",
            "none": "none",
        }
        meter_type = cleaned.get("meter_type")
        if meter_type and cleaned.get("meter_unit") != expected_unit[meter_type]:
            self.add_error("meter_unit", f"وحدة العداد المطلوبة لهذا النوع هي {expected_unit[meter_type]}.")
        return cleaned


class AssetForm(EquipmentForm):
    json_fields = ("specifications",)

    asset_code = forms.CharField(label="رمز المعدة", max_length=50)
    asset_name = forms.CharField(label="اسم المعدة", max_length=200)
    category_id = forms.ChoiceField(label="التصنيف")
    serial_number = forms.CharField(label="الرقم التسلسلي", max_length=120, required=False)
    manufacturer = forms.CharField(label="الشركة المصنعة", max_length=120, required=False)
    model = forms.CharField(label="الطراز", max_length=120, required=False)
    ownership_type = forms.ChoiceField(
        label="نوع الملكية",
        choices=(("owned", "مملوكة"), ("rented", "مستأجرة"), ("leased", "مؤجرة بعقد"),
                 ("borrowed", "معارة")),
    )
    owner_entity_id = forms.UUIDField(label="الجهة المالكة", required=False)
    responsible_entity_id = forms.UUIDField(label="الجهة المسؤولة", required=False)
    custodian_ref_type = forms.CharField(label="نوع مرجع العهدة", max_length=40, required=False)
    custodian_ref_id = forms.CharField(label="مرجع العهدة", max_length=120, required=False)
    home_location = forms.CharField(label="الموقع الأساسي", max_length=300, required=False)
    current_location = forms.CharField(label="الموقع الحالي", max_length=300, required=False)
    lifecycle_status = forms.ChoiceField(
        label="الحالة الحياتية",
        choices=(("in_service", "ضمن الخدمة"), ("suspended", "معلقة"),
                 ("retired", "متقاعدة"), ("disposed", "مستبعدة")),
    )
    meter_initial = forms.DecimalField(label="قراءة العداد الافتتاحية", required=False,
                                       min_value=0, max_digits=20, decimal_places=6)
    acquisition_date = forms.DateField(label="تاريخ الاقتناء", required=False,
                                       widget=forms.DateInput(attrs={"type": "date"}))
    acquisition_value = forms.DecimalField(label="قيمة الاقتناء", required=False,
                                           min_value=0, max_digits=20, decimal_places=4)
    currency_id = forms.UUIDField(label="معرف العملة", required=False)
    rental_contract_ref = forms.CharField(label="مرجع عقد الإيجار", max_length=200, required=False)
    specifications = JsonObjectField(label="المواصفات JSON", required=False, initial="{}",
                                     widget=forms.Textarea(attrs={"rows": 3}))
    notes = forms.CharField(label="ملاحظات", required=False, max_length=4000,
                            widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, categories=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category_id"].choices = [("", "اختر التصنيف")] + [
            (category["id"], f'{category["category_code"]} — {category["name_ar"]}')
            for category in categories if category["is_active"]
        ]

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("acquisition_value") is not None and not cleaned.get("currency_id"):
            self.add_error("currency_id", "العملة مطلوبة عند تسجيل قيمة الاقتناء.")
        if cleaned.get("custodian_ref_id") and not cleaned.get("custodian_ref_type"):
            self.add_error("custodian_ref_type", "نوع مرجع العهدة مطلوب مع رقم المرجع.")
        return cleaned


class AssetCreateForm(EquipmentForm):
    asset_name = forms.CharField(label="اسم المعدة", max_length=200)
    asset_code = forms.CharField(label="رمز المعدة", max_length=50)
    category_id = forms.ChoiceField(label="تصنيف المعدة")
    manufacturer = forms.CharField(label="الشركة المصنعة", max_length=120, required=False)
    model = forms.CharField(label="الموديل", max_length=120, required=False)
    serial_number = forms.CharField(label="الرقم التسلسلي", max_length=120, required=False)
    owner_entity_id = forms.ChoiceField(label="الجهة المالكة", required=False)
    responsible_entity_id = forms.ChoiceField(label="الجهة المسؤولة", required=False)
    current_location = forms.CharField(label="الموقع الابتدائي", max_length=300, required=False)
    ownership_type = forms.ChoiceField(
        label="نوع الملكية",
        choices=(("owned", "مملوكة"), ("rented", "مستأجرة")),
    )
    meter_initial = forms.DecimalField(
        label="القراءة الابتدائية",
        required=False,
        min_value=0,
        max_digits=20,
        decimal_places=6,
    )
    acquisition_date = forms.DateField(
        label="تاريخ الاقتناء",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    acquisition_value = forms.DecimalField(
        label="قيمة الاقتناء",
        required=False,
        min_value=0,
        max_digits=20,
        decimal_places=4,
    )
    currency_id = forms.ChoiceField(label="عملة الاقتناء", required=False)
    notes = forms.CharField(
        label="ملاحظات",
        required=False,
        max_length=4000,
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    def __init__(
        self,
        *args,
        categories=(),
        organization_units=(),
        currencies=(),
        responsible_entity_id=None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.categories_by_id = {str(item["id"]): item for item in categories}
        self.fields["category_id"].choices = [("", "اختر تصنيف المعدة")] + [
            (
                str(item["id"]),
                f'{item["category_code"]} — {item["name_ar"]}',
            )
            for item in categories
        ]
        entity_choices = [("", "اختر الجهة")]
        entity_choices.extend(
            (str(item["id"]), item["name"]) for item in organization_units
        )
        for field_name in ("owner_entity_id", "responsible_entity_id"):
            self.fields[field_name].choices = entity_choices
        if responsible_entity_id:
            normalized_responsible = str(responsible_entity_id).replace("-", "").lower()
            self.fields["responsible_entity_id"].initial = next(
                (
                    value
                    for value, _label in entity_choices
                    if value.replace("-", "").lower() == normalized_responsible
                ),
                "",
            )
        self.fields["currency_id"].choices = [("", "اختر العملة")] + [
            (
                str(item["id"]),
                f'{item["code"]} — {item["name"]}',
            )
            for item in currencies
        ]
        self.fields["asset_name"].widget.attrs["placeholder"] = "مثال: حفارة جنزير"
        self.fields["asset_code"].widget.attrs["placeholder"] = "مثال: EQ-00125"
        self.fields["serial_number"].widget.attrs["placeholder"] = "الرقم المدوّن على لوحة المعدة"
        self.fields["current_location"].widget.attrs["placeholder"] = "مثال: مستودع الموقع الشمالي"
        self.fields["meter_initial"].widget.attrs["inputmode"] = "decimal"
        self.fields["acquisition_value"].widget.attrs["inputmode"] = "decimal"

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("acquisition_value") is not None and not cleaned.get("currency_id"):
            self.add_error("currency_id", "اختر العملة عند تسجيل قيمة الاقتناء.")
        category = self.categories_by_id.get(str(cleaned.get("category_id")))
        if (
            category
            and category.get("meter_type") == "none"
            and cleaned.get("meter_initial") is not None
        ):
            self.add_error("meter_initial", "هذا التصنيف لا يستخدم عداداً.")
        return cleaned

    def payload(self):
        values = super().payload()
        for key in (
            "manufacturer", "model", "serial_number", "owner_entity_id",
            "responsible_entity_id", "current_location", "acquisition_date",
            "acquisition_value", "currency_id", "notes",
        ):
            if values.get(key) in ("", None):
                values.pop(key, None)
        if values.get("current_location"):
            values["home_location"] = values["current_location"]
        return values


class EquipmentRequestForm(EquipmentForm):
    json_fields = ("required_specs",)

    category_id = forms.ChoiceField(label="تصنيف المعدة")
    required_quantity = forms.IntegerField(label="الكمية المطلوبة", min_value=1, max_value=10000)
    required_start = forms.DateTimeField(
        label="بداية الاحتياج",
        input_formats=("%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S"),
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
    )
    required_end = forms.DateTimeField(
        label="نهاية الاحتياج",
        input_formats=("%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S"),
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
    )
    required_specs = JsonObjectField(
        label="المواصفات الدنيا JSON",
        required=False,
        initial="{}",
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    target_location = forms.CharField(label="موقع الاستخدام", max_length=300, required=False)
    purpose = forms.CharField(label="الغرض", max_length=2000, widget=forms.Textarea(attrs={"rows": 2}))
    priority = forms.ChoiceField(
        label="الأولوية",
        choices=(("low", "منخفضة"), ("normal", "عادية"), ("high", "عالية"), ("critical", "حرجة")),
        initial="normal",
    )

    def __init__(self, *args, categories=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category_id"].choices = [("", "اختر التصنيف")] + [
            (category["id"], f'{category["category_code"]} — {category["name_ar"]}')
            for category in categories if category["is_active"]
        ]

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("required_start"), cleaned.get("required_end")
        if start and end and start >= end:
            self.add_error("required_end", "نهاية الاحتياج يجب أن تكون بعد بدايته.")
        return cleaned


class EquipmentRequestPageForm(EquipmentRequestForm):
    """Request form for the dedicated UI-05 route.

    The existing workspace form keeps its historical tenant-default behavior;
    this form exposes the same validated API field explicitly for the focused
    requests workflow.
    """

    requested_entity_id = forms.ChoiceField(label="الجهة الطالبة")

    def __init__(self, *args, organization_units=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["requested_entity_id"].choices = [
            ("", "اختر الجهة الطالبة")
        ] + [
            (str(item["id"]), item["name"])
            for item in organization_units
            if item.get("is_active", True)
        ]


class EquipmentAssignmentPageForm(EquipmentForm):
    """Server-side form for the focused UI-06 assignment workspace."""

    asset_id = forms.ChoiceField(label="المعدة المطلوبة")
    beneficiary_entity_id = forms.ChoiceField(label="الجهة المستفيدة")
    planned_start_at = forms.DateTimeField(
        label="بداية التكليف",
        input_formats=["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M"],
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
    )
    planned_end_at = forms.DateTimeField(
        label="نهاية التكليف",
        input_formats=["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M"],
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
    )
    operator_employee_id = forms.ChoiceField(label="المشغل", required=False)
    purpose = forms.CharField(label="الغرض من التكليف", max_length=2000, widget=forms.Textarea(attrs={"rows": 3}))
    request_id = forms.UUIDField(label="مرجع طلب المعدات", required=False)

    def __init__(self, *args, assets=(), organization_units=(), employees=(), requests=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["asset_id"].choices = [
            ("", "اختر المعدة"),
            *[(str(row.get("id")), f'{row.get("asset_code", "—")} — {row.get("asset_name", "معدة غير مسماة")}') for row in assets],
        ]
        self.fields["beneficiary_entity_id"].choices = [
            ("", "اختر الجهة المستفيدة"),
            *[(str(row.get("id")), row.get("name", "جهة غير مسماة")) for row in organization_units],
        ]
        self.fields["operator_employee_id"].choices = [
            ("", "بدون مشغل — تخطيط فقط"),
            *[(str(row.get("id")), f'{row.get("employee_no", "")} — {row.get("full_name", "موظف")}') for row in employees],
        ]
        self.fields["request_id"].widget = forms.Select(choices=[
            ("", "تكليف داخلي مباشر — دون طلب"),
            *[(str(row.get("id")), f'{row.get("request_code", "طلب")} — {row.get("purpose", "طلب معتمد")}') for row in requests],
        ])

    def clean(self):
        cleaned = super().clean()
        for key in ("planned_start_at", "planned_end_at"):
            value = cleaned.get(key)
            if value and timezone.is_naive(value):
                cleaned[key] = timezone.make_aware(value, timezone.get_current_timezone())
        start = cleaned.get("planned_start_at")
        end = cleaned.get("planned_end_at")
        if start and end and start >= end:
            self.add_error("planned_end_at", "يجب أن تكون نهاية التكليف بعد بدايته.")
        return cleaned


class EquipmentMovementForm(EquipmentForm):
    asset_id = forms.ChoiceField(label="المعدة")
    from_location = forms.CharField(label="الموقع الحالي", max_length=300, required=False)
    to_location = forms.CharField(label="الموقع الوجهة", max_length=300)
    movement_reason = forms.CharField(label="سبب النقل", max_length=2000, widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, assets=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["asset_id"].choices = [("", "اختر المعدة")] + [
            (asset["id"], f'{asset["asset_code"]} — {asset["asset_name"]}')
            for asset in assets
        ]


class InspectionForm(EquipmentForm):
    json_fields = ("findings",)

    asset_id = forms.ChoiceField(label="المعدة")
    assignment_id = forms.UUIDField(label="معرف التكليف قبل التشغيل", required=False)
    inspection_type = forms.ChoiceField(
        label="نوع الفحص",
        choices=(("pre_operation", "قبل التشغيل"), ("post_repair", "بعد الإصلاح"),
                 ("periodic", "دوري"), ("return", "عند الإرجاع")),
    )
    result = forms.ChoiceField(
        label="النتيجة",
        choices=(("passed", "اجتياز"), ("conditional", "مشروط"), ("failed", "فشل")),
    )
    critical_failure = forms.BooleanField(label="إخفاق حرج", required=False)
    checklist_version = forms.CharField(label="إصدار قائمة الفحص", max_length=120)
    findings = JsonObjectField(
        label="النتائج JSON", required=False, initial="{}",
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    meter_reading = forms.DecimalField(
        label="قراءة العداد", required=False, min_value=0, max_digits=20, decimal_places=6,
    )

    def __init__(self, *args, assets=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["asset_id"].choices = [("", "اختر المعدة")] + [
            (asset["id"], f'{asset["asset_code"]} — {asset["asset_name"]}')
            for asset in assets
        ]

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("critical_failure") and cleaned.get("result") != "failed":
            self.add_error("critical_failure", "الإخفاق الحرج يتطلب نتيجة فشل.")
        if cleaned.get("inspection_type") == "pre_operation" and not cleaned.get("assignment_id"):
            self.add_error("assignment_id", "الفحص قبل التشغيل يتطلب معرف تكليف.")
        return cleaned


class MaintenanceForm(EquipmentForm):
    asset_id = forms.ChoiceField(label="المعدة")
    maintenance_type = forms.ChoiceField(
        label="نوع الصيانة",
        choices=(("preventive", "وقائية"), ("corrective", "تصحيحية"), ("emergency", "طارئة")),
    )
    description = forms.CharField(label="وصف العمل", max_length=2000, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, assets=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["asset_id"].choices = [("", "اختر المعدة")] + [
            (asset["id"], f'{asset["asset_code"]} — {asset["asset_name"]}')
            for asset in assets
        ]


class MaintenancePlanForm(EquipmentForm):
    asset_id = forms.ChoiceField(label="المعدة")
    description = forms.CharField(
        label="وصف الصيانة الوقائية",
        max_length=2000,
        widget=forms.Textarea(attrs={"rows": 2}),
    )
    interval_days = forms.IntegerField(
        label="الفاصل بالأيام",
        required=False,
        min_value=1,
        max_value=36500,
    )
    first_due_at = forms.DateTimeField(
        label="أول استحقاق زمني",
        required=False,
        input_formats=("%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S"),
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
    )
    interval_meter = forms.DecimalField(
        label="فاصل العداد التراكمي",
        required=False,
        min_value=0,
        max_digits=20,
        decimal_places=6,
    )
    first_due_meter = forms.DecimalField(
        label="أول استحقاق للعداد المعياري",
        required=False,
        min_value=0,
        max_digits=20,
        decimal_places=6,
    )
    idempotency_key = forms.CharField(
        widget=forms.HiddenInput,
        initial=uuid4().hex,
    )

    def __init__(self, *args, assets=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["asset_id"].choices = [("", "اختر المعدة")] + [
            (asset["id"], f'{asset["asset_code"]} — {asset["asset_name"]}')
            for asset in assets
        ]
        if not self.is_bound:
            self.initial["idempotency_key"] = uuid4().hex

    def clean_first_due_at(self):
        value = self.cleaned_data.get("first_due_at")
        if value and timezone.is_naive(value):
            return timezone.make_aware(value, timezone.get_current_timezone())
        return value

    def clean(self):
        cleaned = super().clean()
        intervals = (
            ("interval_days", "first_due_at"),
            ("interval_meter", "first_due_meter"),
        )
        if not any(cleaned.get(interval) is not None for interval, _ in intervals):
            self.add_error("interval_days", "أدخل فاصلاً زمنياً أو فاصل عداد واحداً على الأقل.")
        for interval, first_due in intervals:
            if (cleaned.get(interval) is None) != (cleaned.get(first_due) is None):
                self.add_error(first_due, "قيمة أول استحقاق مطلوبة مع الفاصل المقابل.")
        return cleaned


class MeterEventForm(EquipmentForm):
    asset_id = forms.ChoiceField(label="المعدة")
    event_type = forms.ChoiceField(
        label="نوع حدث العداد",
        choices=(("reading", "قراءة"), ("replacement", "استبدال"), ("correction", "تصحيح تاريخي")),
    )
    reading_value = forms.DecimalField(
        label="القراءة",
        required=False,
        min_value=0,
        max_digits=20,
        decimal_places=6,
    )
    old_final_reading = forms.DecimalField(
        label="آخر قراءة للعداد السابق",
        required=False,
        min_value=0,
        max_digits=20,
        decimal_places=6,
    )
    new_initial_reading = forms.DecimalField(
        label="القراءة الافتتاحية للعداد الجديد",
        required=False,
        min_value=0,
        max_digits=20,
        decimal_places=6,
    )
    correction_of_event_id = forms.ChoiceField(label="القراءة المعتمدة", required=False)
    corrected_reading = forms.DecimalField(
        label="القراءة المصححة",
        required=False,
        min_value=0,
        max_digits=20,
        decimal_places=6,
    )
    reason_code = forms.CharField(label="سبب الاستبدال أو التصحيح", max_length=120, required=False)
    evidence_ref = forms.CharField(label="مرجع الإثبات", max_length=500, required=False)
    event_at = forms.DateTimeField(
        label="وقت القراءة",
        required=False,
        input_formats=("%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S"),
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
    )
    idempotency_key = forms.CharField(widget=forms.HiddenInput, initial=uuid4().hex)

    def __init__(self, *args, assets=(), approved_readings=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["asset_id"].choices = [("", "اختر المعدة")] + [
            (asset["id"], f'{asset["asset_code"]} — {asset["asset_name"]}')
            for asset in assets
        ]
        self.fields["correction_of_event_id"].choices = [("", "اختر قراءة معتمدة")] + [
            (event["id"], f'{event["event_code"]} — {event["reading_value"]} {event["meter_unit_snapshot"]}')
            for event in approved_readings
            if event["event_type"] == "reading" and event["status"] == "approved"
        ]
        if not self.is_bound:
            self.initial["idempotency_key"] = uuid4().hex

    def clean_event_at(self):
        value = self.cleaned_data.get("event_at")
        if value and timezone.is_naive(value):
            return timezone.make_aware(value, timezone.get_current_timezone())
        return value

    def clean(self):
        cleaned = super().clean()
        event_type = cleaned.get("event_type")
        requirements = {
            "reading": ("reading_value",),
            "replacement": ("old_final_reading", "new_initial_reading", "reason_code", "evidence_ref"),
            "correction": ("correction_of_event_id", "corrected_reading", "reason_code", "evidence_ref"),
        }
        for field in requirements.get(event_type, ()):
            if cleaned.get(field) in (None, ""):
                self.add_error(field, "هذا الحقل مطلوب لنوع الحدث المحدد.")
        return cleaned

    def payload(self):
        event_type = self.cleaned_data["event_type"]
        values = super().payload()
        values.pop("event_type", None)
        keep = {
            "reading": {"reading_value"},
            "replacement": {"old_final_reading", "new_initial_reading", "reason_code", "evidence_ref"},
            "correction": {"correction_of_event_id", "corrected_reading", "reason_code", "evidence_ref"},
        }[event_type]
        optional = {
            "reading_value", "old_final_reading", "new_initial_reading",
            "correction_of_event_id", "corrected_reading", "reason_code", "evidence_ref",
        }
        for field in optional - keep:
            values.pop(field, None)
        return values


class FuelEventForm(EquipmentForm):
    asset_id = forms.ChoiceField(label="المعدة")
    event_type = forms.ChoiceField(
        label="نوع حركة الوقود التشغيلية",
        choices=(
            ("opening", "رصيد افتتاحي"),
            ("issued", "تسليم تشغيلي للمعدة"),
            ("consumed", "استهلاك مقاس"),
            ("returned", "إرجاع"),
            ("adjustment_in", "تعديل موجب"),
            ("adjustment_out", "تعديل سالب"),
        ),
    )
    related_issue_event_id = forms.ChoiceField(
        label="سند الصرف التشغيلي الأصلي (اختياري للمرتجع)",
        required=False,
    )
    energy_type = forms.ChoiceField(
        label="نوع الطاقة",
        choices=(("diesel", "ديزل"), ("gasoline", "بنزين"),
                 ("electricity", "كهرباء"), ("other", "أخرى")),
    )
    quantity = forms.DecimalField(
        label="الكمية",
        min_value=0,
        max_digits=20,
        decimal_places=6,
    )
    unit = forms.ChoiceField(
        label="الوحدة",
        choices=(("L", "لتر"), ("kWh", "كيلوواط ساعة"), ("kg", "كغ"), ("m3", "م³")),
    )
    event_at = forms.DateTimeField(
        label="وقت الحركة",
        required=False,
        input_formats=("%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S"),
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
    )
    unit_cost = forms.DecimalField(
        label="تكلفة الوحدة الاختيارية",
        required=False,
        min_value=0,
        max_digits=20,
        decimal_places=6,
    )
    currency_id = forms.UUIDField(label="معرف عملة Core", required=False)
    reason_code = forms.CharField(label="سبب التعديل", max_length=120, required=False)
    notes = forms.CharField(label="ملاحظات", max_length=2000, required=False)
    idempotency_key = forms.CharField(widget=forms.HiddenInput, initial=uuid4().hex)

    def __init__(self, *args, assets=(), issued_events=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["asset_id"].choices = [("", "اختر المعدة")] + [
            (asset["id"], f'{asset["asset_code"]} — {asset["asset_name"]}')
            for asset in assets
        ]
        self.fields["related_issue_event_id"].choices = [("", "بدون ربط مخزني")] + [
            (
                event["id"],
                f'{event["fuel_event_code"]} — {event["quantity"]} {event["unit"]}',
            )
            for event in issued_events
            if event.get("event_type") == "issued" and event.get("status") == "posted"
        ]
        if not self.is_bound:
            self.initial["idempotency_key"] = uuid4().hex

    def clean_event_at(self):
        value = self.cleaned_data.get("event_at")
        if value and timezone.is_naive(value):
            return timezone.make_aware(value, timezone.get_current_timezone())
        return value

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("quantity") is not None and cleaned["quantity"] <= 0:
            self.add_error("quantity", "الكمية يجب أن تكون أكبر من صفر.")
        if (cleaned.get("unit_cost") is None) != (cleaned.get("currency_id") is None):
            self.add_error("currency_id", "معرف العملة مطلوب مع تكلفة الوحدة.")
        if cleaned.get("event_type") in ("adjustment_in", "adjustment_out") and not cleaned.get("reason_code"):
            self.add_error("reason_code", "سبب التعديل مطلوب.")
        if cleaned.get("related_issue_event_id") and cleaned.get("event_type") != "returned":
            self.add_error(
                "related_issue_event_id",
                "لا يمكن ربط حدث الصرف الأصلي إلا بحركة إرجاع.",
            )
        return cleaned


class PartInstallForm(EquipmentForm):
    inventory_item_id = forms.UUIDField(label="معرف صنف Inventory")
    mount_position = forms.CharField(label="موضع التركيب", max_length=120)
    part_serial_number = forms.CharField(label="الرقم التسلسلي", max_length=120, required=False)
    lot_number = forms.CharField(label="رقم الدفعة", max_length=120, required=False)
    installed_at = forms.DateTimeField(
        label="تاريخ التركيب",
        input_formats=("%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S"),
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
    )
    maintenance_order_id = forms.UUIDField(label="معرف أمر الصيانة", required=False)
    installation_inventory_document_id = forms.UUIDField(
        label="معرف سند الصرف المرحّل في Inventory"
    )
    idempotency_key = forms.CharField(widget=forms.HiddenInput, initial=uuid4().hex)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            self.initial["idempotency_key"] = uuid4().hex
            self.initial["installed_at"] = timezone.localtime().replace(second=0, microsecond=0)

    def clean_installed_at(self):
        value = self.cleaned_data["installed_at"]
        if timezone.is_naive(value):
            value = timezone.make_aware(value, timezone.get_current_timezone())
        return value


class PartRemovalForm(EquipmentForm):
    lifecycle_id = forms.UUIDField(widget=forms.HiddenInput)
    removed_at = forms.DateTimeField(
        label="تاريخ الإزالة",
        input_formats=("%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S"),
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
    )
    reason_code = forms.CharField(label="سبب الإزالة", max_length=120)
    removal_inventory_document_id = forms.UUIDField(
        label="معرف سند الإرجاع المرحّل في Inventory"
    )
    idempotency_key = forms.CharField(widget=forms.HiddenInput, initial=uuid4().hex)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            self.initial["idempotency_key"] = uuid4().hex
            self.initial["removed_at"] = timezone.localtime().replace(second=0, microsecond=0)

    def clean_removed_at(self):
        value = self.cleaned_data["removed_at"]
        if timezone.is_naive(value):
            value = timezone.make_aware(value, timezone.get_current_timezone())
        return value


class PartReplacementForm(PartInstallForm):
    lifecycle_id = forms.UUIDField(widget=forms.HiddenInput)
    removed_at = forms.DateTimeField(
        label="تاريخ إزالة القطعة القديمة",
        input_formats=("%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S"),
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
    )
    removal_reason_code = forms.CharField(label="سبب الاستبدال", max_length=120)
    removal_inventory_document_id = forms.UUIDField(
        label="معرف سند إرجاع القطعة القديمة في Inventory"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            self.initial["removed_at"] = timezone.localtime().replace(second=0, microsecond=0)

    def clean_removed_at(self):
        value = self.cleaned_data["removed_at"]
        if timezone.is_naive(value):
            value = timezone.make_aware(value, timezone.get_current_timezone())
        return value


class MaintenanceCompletionForm(EquipmentForm):
    completion_notes = forms.CharField(
        label="ملاحظات الإكمال الفني",
        max_length=2000,
        widget=forms.Textarea(attrs={"rows": 2}),
    )


class SafetyReleaseForm(EquipmentForm):
    inspection_id = forms.ChoiceField(label="فحص ما بعد الإصلاح")

    def __init__(self, *args, inspections=(), **kwargs):
        super().__init__(*args, **kwargs)
        choices = [
            (row["id"], f'{row["id"][:12]} — {row["inspected_at"]}')
            for row in inspections
            if row["inspection_type"] == "post_repair"
            and row["result"] == "passed"
            and row["status"] == "verified"
        ]
        self.fields["inspection_id"].choices = [("", "اختر فحصاً مجتازاً ومتحققاً")] + choices


class FuelInventoryMappingForm(EquipmentForm):
    category_id = forms.ChoiceField(label="تصنيف المعدات")
    energy_type = forms.ChoiceField(
        label="نوع الطاقة",
        choices=(
            ("diesel", "ديزل"),
            ("gasoline", "بنزين"),
            ("electricity", "كهرباء"),
            ("other", "أخرى"),
        ),
    )
    item_id = forms.ChoiceField(label="صنف المخزون")
    warehouse_id = forms.ChoiceField(label="المخزن")

    def __init__(self, *args, categories=(), items=(), warehouses=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category_id"].choices = [
            (str(row["id"]), f'{row["category_code"]} — {row["name_ar"]}')
            for row in categories if row.get("fuel_unit")
        ]
        self.fields["item_id"].choices = [
            (str(row["id"]), f'{row["code"]} — {row["name_ar"]}')
            for row in items if row.get("base_unit_id")
        ]
        self.fields["warehouse_id"].choices = [
            (str(row["id"]), f'{row["code"]} — {row["name"]}')
            for row in warehouses
        ]
