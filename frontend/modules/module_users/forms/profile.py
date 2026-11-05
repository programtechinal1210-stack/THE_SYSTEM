# modules/module_users/forms/profile.py
from django import forms
from .base import BaseUserForm

class UserProfileForm(BaseUserForm):
    full_name = forms.CharField(max_length=200, label="الاسم الكامل", widget=forms.TextInput(attrs={"placeholder": "أدخل الاسم الكامل"}))
    email = forms.EmailField(label="البريد الإلكتروني", widget=forms.EmailInput(attrs={"placeholder": "أدخل البريد الإلكتروني"}))
    phone = forms.CharField(max_length=20, required=False, label="رقم الجوال", widget=forms.TextInput(attrs={"placeholder": "أدخل رقم الجوال"}))
    current_password = forms.CharField(max_length=128, required=False, label="كلمة المرور الحالية", widget=forms.PasswordInput(attrs={"placeholder": "أدخل كلمة المرور الحالية"}))
    new_password = forms.CharField(max_length=128, required=False, label="كلمة المرور الجديدة", widget=forms.PasswordInput(attrs={"placeholder": "أدخل كلمة المرور الجديدة"}))
    confirm_password = forms.CharField(max_length=128, required=False, label="تأكيد كلمة المرور الجديدة", widget=forms.PasswordInput(attrs={"placeholder": "أعد إدخال كلمة المرور الجديدة"}))
    
    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get("new_password")
        confirm_password = cleaned_data.get("confirm_password")
        if new_password and confirm_password and new_password != confirm_password:
            self.add_error("confirm_password", "كلمة المرور غير متطابقة")
        return cleaned_data
