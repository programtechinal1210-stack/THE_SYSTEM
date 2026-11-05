# modules/module_users/tests/test_forms.py
from django.test import TestCase
from ..forms.create import UserCreateForm

class UserFormsTest(TestCase):
    def test_create_form_valid(self):
        form = UserCreateForm({"username":"test","password":"pass123","confirm_password":"pass123","full_name":"مستخدم اختبار","email":"test@test.com","role":"viewer"})
        self.assertTrue(form.is_valid())
