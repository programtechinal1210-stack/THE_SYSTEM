# modules/module_notifications/services/filter.py
from .base import BaseNotificationService

class NotificationFilterService(BaseNotificationService):
    def filter_notifications(self, user_id, filters=None):
        notifications = self.get_user_notifications(user_id)
        if not filters: return notifications
        if filters.get("is_read") == "true": notifications = [n for n in notifications if n.get("is_read")]
        elif filters.get("is_read") == "false": notifications = [n for n in notifications if not n.get("is_read")]
        if filters.get("type"): notifications = [n for n in notifications if n.get("type") == filters["type"]]
        return sorted(notifications, key=lambda x: x.get("created_at", ""), reverse=True)
    
    def get_unread_count(self, user_id):
        return len([n for n in self.get_user_notifications(user_id) if not n.get("is_read")])
