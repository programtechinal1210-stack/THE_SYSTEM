# modules/module_users/services/filter.py
from shared.services.api_client import ApiClient, ApiException

class UserFilterService:
    def __init__(self):
        self.client = ApiClient()

    def filter_users(self, filters=None):
        params = {k: v for k, v in (filters or {}).items() if v}
        try:
            result = self.client.get('/users/', params=params)
            return result if isinstance(result, list) else result.get('items', [])
        except ApiException:
            return []

    def get_filter_options(self):
        try:
            stats = self.client.get('/reports/dashboard')
            users_stats = stats.get('users', {})
            return {
                'total': users_stats.get('total', 0),
                'active': users_stats.get('active', 0),
                'inactive': users_stats.get('inactive', 0),
            }
        except:
            return {'total': 0, 'active': 0, 'inactive': 0}
