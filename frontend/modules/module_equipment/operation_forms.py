from django import forms
from django.utils import timezone


class SafetyPolicyForm(forms.Form):
    policy_version = forms.IntegerField(label="رقم الإصدار", min_value=1)
    policy_mode = forms.ChoiceField(
        label="نوع السياسة",
        choices=(("production", "إنتاجية"), ("test", "اختبار معزول")),
    )
    policy_reference = forms.CharField(label="مرجع السياسة", max_length=120)
    policy_document_ref = forms.CharField(label="مرجع الوثيقة", max_length=500)
    issuing_authority = forms.CharField(label="الجهة المصدرة", max_length=200)
    authorized_role_code = forms.CharField(label="رمز دور الاعتماد", max_length=120)
    effective_from = forms.DateTimeField(
        label="تاريخ السريان",
        input_formats=("%Y-%m-%dT%H:%M",),
        widget=forms.DateTimeInput(format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"}),
    )
    inspection_validity_minutes = forms.IntegerField(
        label="صلاحية الفحص بالدقائق", min_value=1, max_value=1440
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["effective_from"].initial = timezone.localtime()
        for field in self.fields.values():
            field.widget.attrs.setdefault(
                "class", "form-select" if isinstance(field, forms.ChoiceField) else "form-control"
            )

    def payload(self, organization_id):
        values = dict(self.cleaned_data)
        values["organization_id"] = str(organization_id)
        effective_from = values["effective_from"]
        if timezone.is_naive(effective_from):
            effective_from = timezone.make_aware(effective_from, timezone.get_current_timezone())
        values["effective_from"] = effective_from.isoformat()
        return values


class OperationStartForm(forms.Form):
    assignment_id = forms.ChoiceField(label="التكليف")
    shift_roster_id = forms.ChoiceField(label="وردية المشغل")
    policy_id = forms.ChoiceField(label="سياسة السلامة المعتمدة")
    notes = forms.CharField(label="ملاحظات", required=False, max_length=2000)

    def __init__(self, *args, assignments=(), rosters=(), policies=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assignment_id"].choices = [("", "اختر التكليف")] + [
            (row["id"], f'{row.get("asset_code", row["asset_id"])} — {row["purpose"]}')
            for row in assignments if row["status"] in ("approved", "active")
        ]
        self.fields["shift_roster_id"].choices = [("", "اختر الوردية")] + [
            (row["id"], f'{row["business_date"]} — {row["start_at"]} إلى {row["end_at"]}')
            for row in rosters if row["status"] == "confirmed"
        ]
        self.fields["policy_id"].choices = [("", "اختر السياسة")] + [
            (row["id"], f'{row["policy_reference"]} — v{row["policy_version"]} ({row["policy_mode"]})')
            for row in policies if row["status"] == "approved"
        ]
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-select" if isinstance(field, forms.ChoiceField) else "form-control")

    def payload(self, idempotency_key):
        values = dict(self.cleaned_data)
        values.update({
            "assignment_id": str(values["assignment_id"]),
            "shift_roster_id": str(values["shift_roster_id"]),
            "policy_id": str(values["policy_id"]),
            "idempotency_key": idempotency_key,
        })
        return values


class OperationFinishForm(forms.Form):
    meter_end = forms.DecimalField(
        label="قراءة نهاية العداد", required=False, min_value=0,
        max_digits=20, decimal_places=6,
    )
    working_minutes = forms.IntegerField(label="دقائق العمل", min_value=0)
    idle_minutes = forms.IntegerField(label="دقائق الخمول", min_value=0)
    downtime_minutes = forms.IntegerField(label="دقائق التوقف", min_value=0)
    downtime_reason_code = forms.CharField(label="رمز سبب التوقف", required=False, max_length=120)
    produced_quantity = forms.DecimalField(
        label="الإنتاج الفعلي", required=False, min_value=0,
        max_digits=20, decimal_places=6,
    )
    production_unit = forms.CharField(label="وحدة الإنتاج", required=False, max_length=120)
    fuel_consumed = forms.DecimalField(
        label="الوقود المستهلك", required=False, min_value=0.000001,
        max_digits=20, decimal_places=6,
    )
    fuel_energy_type = forms.ChoiceField(
        label="مصدر الطاقة",
        choices=(("", "غير مسجل"), ("diesel", "ديزل"), ("gasoline", "بنزين"),
                 ("electricity", "كهرباء"), ("other", "أخرى")),
        required=False,
    )
    fuel_unit = forms.ChoiceField(
        label="وحدة الوقود",
        choices=(("", "غير مسجل"), ("L", "لتر"), ("kWh", "كيلوواط ساعة"),
                 ("kg", "كيلوغرام"), ("m3", "متر مكعب")),
        required=False,
    )
    downtime_notes = forms.CharField(label="تفاصيل التوقف", required=False, max_length=2000)
    notes = forms.CharField(label="ملاحظات الإقفال", required=False, max_length=2000)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault(
                "class", "form-select" if isinstance(field, forms.ChoiceField) else "form-control"
            )

    def clean(self):
        cleaned = super().clean()
        pairs = (
            ("produced_quantity", "production_unit"),
            ("fuel_consumed", "fuel_energy_type"),
            ("fuel_consumed", "fuel_unit"),
        )
        for quantity, unit in pairs:
            if (cleaned.get(quantity) is None) != (not cleaned.get(unit)):
                self.add_error(quantity, "يجب إدخال الكمية ووحدتها معاً.")
        if cleaned.get("downtime_minutes") and not cleaned.get("downtime_reason_code"):
            self.add_error("downtime_reason_code", "سبب التوقف مطلوب عند تسجيل مدة توقف.")
        return cleaned

    def payload(self):
        values = dict(self.cleaned_data)
        for key in ("meter_end", "produced_quantity", "fuel_consumed"):
            if values.get(key) is not None:
                values[key] = str(values[key])
        return {key: value for key, value in values.items() if value not in (None, "")}


class AuthorityReferenceForm(forms.Form):
    decision_authority_ref = forms.CharField(label="مرجع قرار الاعتماد", max_length=500)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["decision_authority_ref"].widget.attrs["class"] = "form-control"
