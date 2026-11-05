# modules/module_users/forms/search.py
from django import forms
from .base import BaseUserForm

class UserSearchForm(BaseUserForm):
    query = forms.CharField(label="بحث", widget=forms.TextInput(attrs={"placeholder": "ابحث عن مستخدم...", "class": "form-control w-full"}))
    
    def clean_query(self):
        query = self.cleaned_data.get("query", "")
        if query and len(query) < 2:
            raise forms.ValidationError("يرجى إدخال حرفين على الأقل للبحث")
        return query
