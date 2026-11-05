# modules/module_notifications/tests/test_services.py
from django.test import TestCase
from ..services.crud import NotificationCRUDService
from ..services.filter import NotificationFilterService
from data.arrays import NOTIFICATIONS, generate_id, now

class NotificationServicesTest(TestCase):
    def setUp(self):
        self.crud_service = NotificationCRUDService()
        self.filter_service = NotificationFilterService()
        self.test_notification = {"id":generate_id(),"user_id":"test-user-1","title":"إشعار اختبار","content":"محتوى الإشعار","type":"info","is_read":False,"created_at":now()}
        NOTIFICATIONS.append(self.test_notification)
    
    def test_filter_service_get_unread_count(self):
        count = self.filter_service.get_unread_count("test-user-1")
        self.assertGreaterEqual(count, 1)
    
    def test_crud_service_mark_read(self):
        result = self.crud_service.mark_read(self.test_notification["id"])
        self.assertTrue(result)
    
    def tearDown(self):
        global NOTIFICATIONS
        NOTIFICATIONS = [n for n in NOTIFICATIONS if n.get("id") != self.test_notification["id"]]
