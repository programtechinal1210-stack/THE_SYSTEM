# modules/module_auth/tests/test_services.py
from django.test import TestCase
from ..services.login import LoginService
from ..services.register import RegisterService
from ..services.password import PasswordService
from data.arrays import USERS, get_user_by_username

class AuthServicesTest(TestCase):
    def setUp(self):
        self.test_user = {"id": "test-id-123", "username": "testuser", "password": "TestPass123",
                         "full_name": "مستخدم اختبار", "email": "test@example.com",
                         "role": "viewer", "is_active": True, "created_at": "2026-01-01 00:00:00"}
        USERS.append(self.test_user)
    
    def test_login_service_authenticate_success(self):
        result = LoginService().authenticate("testuser", "TestPass123")
        self.assertTrue(result["success"])
    
    def test_login_service_authenticate_fail(self):
        result = LoginService().authenticate("wronguser", "wrongpass")
        self.assertFalse(result["success"])
    
    def test_password_service_validate_password_valid(self):
        result = PasswordService().validate_password("StrongPass123")
        self.assertTrue(result["valid"])
    
    def test_password_service_validate_password_weak(self):
        result = PasswordService().validate_password("weak")
        self.assertFalse(result["valid"])
    
    def tearDown(self):
        global USERS
        USERS = [u for u in USERS if u.get("id") != "test-id-123"]
