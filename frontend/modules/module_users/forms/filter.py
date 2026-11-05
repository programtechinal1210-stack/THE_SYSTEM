# modules/module_users/forms/filter.py
from django import forms
from .base import BaseUserForm

class UserFilterForm(BaseUserForm):
    role = forms.ChoiceField(required=False, choices=[("", "الكل"), ("admin", "مدير النظام"), ("manager", "مدير المكتب"), ("reviewer", "مراجع"), ("executor", "منفذ"), ("secretary", "سكرتارية"), ("followup", "متابعة"), ("viewer", "مطلع")], label="الدور")
    is_active = forms.ChoiceField(required=False, choices=[("", "الكل"), ("true", "نشط"), ("false", "غير نشط")], label="الحالة")
    search = forms.CharField(required=False, label="بحث", widget=forms.TextInput(attrs={"placeholder": "بحث في الاسم أو اسم المستخدم"}))
