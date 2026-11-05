# modules/module_users/services/export.py
from shared.services.api_client import ApiClient, ApiException
import json

class UserExportService:
    def __init__(self):
        self.client = ApiClient()

    def get_users(self, params=None):
        try:
            result = self.client.get('/users/', params=params or {})
            return result if isinstance(result, list) else result.get('items', [])
        except ApiException:
            return []

    def export_to_json(self, params=None):
        users = self.get_users(params)
        export_data = [{k: v for k, v in u.items() if k != 'password_hash'} for u in users]
        return json.dumps(export_data, ensure_ascii=False, indent=2, default=str)

    def export_to_csv(self, params=None):
        users = self.get_users(params)
        if not users:
            return ''
        headers = ['username', 'full_name', 'email', 'phone', 'position', 'is_active', 'created_at']
        rows = []
        for u in users:
            roles = u.get('roles', [])
            role_name = roles[0] if roles else ''
            if isinstance(role_name, dict):
                role_name = role_name.get('name', '')
            row = [
                str(u.get('username', '')),
                str(u.get('full_name', '')),
                str(u.get('email', '')),
                str(u.get('phone', '')),
                str(role_name),
                str(u.get('position', '')),
                str(u.get('is_active', '')),
                str(u.get('created_at', '')),
            ]
            rows.append(row)
        csv = ','.join(headers) + '\n'
        csv += '\n'.join([','.join([f'\"{r}\"' for r in row]) for row in rows])
        return csv
