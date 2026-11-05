# modules/module_auth/tests/test_forms.py
from django.test import TestCase
from ..forms.login import LoginForm
from ..forms.register import RegisterForm

class AuthFormsTest(TestCase):
    def test_login_form_valid(self):
        form = LoginForm({"username": "admin", "password": "admin123"})
        self.assertTrue(form.is_valid())
    
    def test_login_form_invalid(self):
        form = LoginForm({"username": "", "password": ""})
        self.assertFalse(form.is_valid())
    
    def test_register_form_valid(self):
        form = RegisterForm({
            "username": "newuser", "password": "Password123",
            "confirm_password": "Password123", "full_name": "مستخدم جديد",
            "email": "new@example.com"
        })
        self.assertTrue(form.is_valid())
