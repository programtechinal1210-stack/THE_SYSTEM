# modules/module_users/forms/edit.py
from django import forms
from .base import BaseUserForm

class UserEditForm(BaseUserForm):
    full_name = forms.CharField(max_length=200, label="الاسم الكامل", widget=forms.TextInput(attrs={"placeholder": "أدخل الاسم الكامل"}))
    email = forms.EmailField(label="البريد الإلكتروني", widget=forms.EmailInput(attrs={"placeholder": "أدخل البريد الإلكتروني"}))
    phone = forms.CharField(max_length=20, required=False, label="رقم الجوال", widget=forms.TextInput(attrs={"placeholder": "أدخل رقم الجوال"}))
    position = forms.CharField(max_length=100, required=False, label="المنصب", widget=forms.TextInput(attrs={"placeholder": "أدخل المنصب"}))
    role = forms.ChoiceField(choices=[], label="الدور")
    password = forms.CharField(max_length=128, required=False, label="كلمة المرور الجديدة", widget=forms.PasswordInput(attrs={"placeholder": "اترك فارغاً إذا لم ترغب في التغيير"}))
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["role"].choices = [("admin", "مدير النظام"), ("manager", "مدير المكتب"), ("reviewer", "مراجع"), ("executor", "منفذ"), ("secretary", "سكرتارية"), ("followup", "متابعة"), ("viewer", "مطلع")]
