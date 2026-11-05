# modules/module_notifications/tests/test_forms.py
from django.test import TestCase
from ..forms.filter import NotificationFilterForm

class NotificationFormsTest(TestCase):
    def test_filter_form_valid(self):
        form = NotificationFilterForm({"is_read": "false", "type": "info"})
        self.assertTrue(form.is_valid())
    
    def test_filter_form_invalid(self):
        form = NotificationFilterForm({"is_read": "invalid"})
        self.assertFalse(form.is_valid())
