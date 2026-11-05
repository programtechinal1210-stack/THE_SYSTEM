"""Compatibility facade over the current Core API; no fallback data."""
from urllib.parse import quote
from shared.services.api_client import ApiClient

class SettingsService:
    def __init__(self): self.client = ApiClient()
    def get_categories(self): return self.client.get('/settings/categories')
    def get_system_setting(self, key): return self.client.get('/settings/by-key/' + quote(key, safe=''))
    def update_system_setting(self, key, value): return self.client.put('/settings/by-key/' + quote(key, safe=''), {'value': value})
    def get_all_system_settings(self): return self.client.get('/settings')
    def get_user_settings(self): return self.client.get('/user-settings/effective')
    def update_user_setting(self, key, value): return self.client.put('/user-settings/' + quote(key, safe=''), {'value': value})
    def get_notification_settings(self): return self.client.get('/user-notification-settings/available')
    def get_notification_channels(self): return self.client.get('/notifications/channels')
    def get_notifications(self, limit=20): return self.client.get('/notifications', {'limit': limit})
    def get_unread_count(self): return self.client.get('/notifications/unread-count')
    def mark_read(self, identifier): return self.client.put('/notifications/mark-read/' + quote(str(identifier), safe=''))
    def mark_all_read(self): return self.client.put('/notifications/mark-all-read')
    def change_password(self, current, new): return self.client.put('/profile/password', {'current_password': current, 'new_password': new})

settings_service = SettingsService()
