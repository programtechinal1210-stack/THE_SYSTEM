# shared/components/form.py
from django.utils.safestring import mark_safe

class Form:
    def __init__(self, form_instance, submit_text="حفظ", cancel_url=None, method="post", **kwargs):
        self.form = form_instance; self.submit_text = submit_text; self.cancel_url = cancel_url
        self.method = method; self.attrs = kwargs
    
    def render(self):
        html = f'<form method="{self.method}" class="space-y-4" {" ".join([f"{k}={v}" for k,v in self.attrs.items()])}><div class="grid grid-cols-1 md:grid-cols-2 gap-4">'
        for field in self.form: html += self.render_field(field)
        html += '</div><div class="flex gap-2 mt-4 pt-4 border-t border-gray-200">'
        html += f'<button type="submit" class="btn btn-primary">{self.submit_text}</button>'
        if self.cancel_url: html += f'<a href="{self.cancel_url}" class="btn btn-outline">إلغاء</a>'
        html += '</div></form>'
        return mark_safe(html)
    
    def render_field(self, field):
        error_html = f'<span class="text-red-600 text-sm">{field.errors[0]}</span>' if field.errors else ''
        help_html = f'<span class="text-gray-500 text-sm">{field.help_text}</span>' if field.help_text else ''
        return f'<div class="form-group"><label for="{field.id_for_label}" class="block text-sm font-medium text-gray-700 mb-1">{field.label}{"" if field.field.required else " <span class=\"text-gray-400 text-sm\">(اختياري)</span>"}</label>{field}{help_html}{error_html}</div>'
