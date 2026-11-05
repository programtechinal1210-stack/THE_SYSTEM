# modules/module_users/tests/test_services.py
from django.test import TestCase
from ..services.crud import UserCRUDService
from data.arrays import USERS, generate_id, now

class UserServicesTest(TestCase):
    def setUp(self):
        self.service = UserCRUDService()
        self.test_user = {"id":generate_id(),"username":"testuser","full_name":"مستخدم اختبار","created_at":now()}
        USERS.append(self.test_user)
    
    def test_get_user(self):
        self.assertIsNotNone(self.service.get_user(self.test_user["id"]))
    
    def tearDown(self):
        global USERS
        USERS = [u for u in USERS if u.get("id") != self.test_user["id"]]
