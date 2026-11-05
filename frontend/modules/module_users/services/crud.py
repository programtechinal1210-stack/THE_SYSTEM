# modules/module_users/services/crud.py
from shared.services.api_client import ApiClient, ApiException

class UserCRUDService:
    def __init__(self):
        self.client = ApiClient()

    def get_all(self, params=None):
        try:
            result = self.client.get('/users/', params=params or {})
            return result if isinstance(result, list) else result.get('items', [])
        except ApiException:
            return []

    def get_by_id(self, user_id):
        try:
            return self.client.get(f'/users/{user_id}')
        except ApiException:
            return None

    def create(self, data):
        try:
            return self.client.post('/auth/register', data)
        except ApiException as e:
            return {'success': False, 'error': str(e)}

    def update(self, user_id, data):
        try:
            return self.client.put(f'/users/{user_id}', data)
        except ApiException as e:
            return {'success': False, 'error': str(e)}

    def delete(self, user_id):
        try:
            self.client.delete(f'/users/{user_id}')
            return True
        except ApiException:
            return False

    def update_status(self, user_id, is_active):
        return self.update(user_id, {'is_active': is_active})
