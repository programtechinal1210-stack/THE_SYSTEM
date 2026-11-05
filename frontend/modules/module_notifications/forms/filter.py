# modules/module_notifications/forms/filter.py
from django import forms
from .base import BaseNotificationForm

class NotificationFilterForm(BaseNotificationForm):
    is_read = forms.ChoiceField(required=False, choices=[("", "الكل"), ("false", "غير مقروءة"), ("true", "مقروءة")], label="الحالة")
    type = forms.ChoiceField(required=False, choices=[("", "الكل"), ("info", "معلومات"), ("success", "نجاح"), ("warning", "تحذير"), ("danger", "خطأ")], label="النوع")
