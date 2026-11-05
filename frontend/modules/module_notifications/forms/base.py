# modules/module_notifications/forms/base.py
from django import forms

class BaseNotificationForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if hasattr(field.widget, "attrs"):
                field.widget.attrs["class"] = field.widget.attrs.get("class", "") + " form-control"
