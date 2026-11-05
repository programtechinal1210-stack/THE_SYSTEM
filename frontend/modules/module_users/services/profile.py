# modules/module_users/services/profile.py
from shared.services.api_client import ApiClient, ApiException

class UserProfileService:
    def __init__(self):
        self.client = ApiClient()

    def get_profile(self):
        try:
            return self.client.get('/auth/me')
        except ApiException:
            return None

    def update_profile(self, user_id, data):
        try:
            return self.client.put(f'/users/{user_id}', data)
        except ApiException as e:
            return {'success': False, 'error': str(e)}

    def change_password(self, user_id, current_password, new_password):
        try:
            return self.client.put(f'/users/{user_id}/password', {
                'current_password': current_password,
                'new_password': new_password
            })
        except ApiException as e:
            return {'success': False, 'error': str(e)}

    def get_stats(self, user_id):
        stats = {'total_cases': 0, 'total_tasks': 0, 'completed_tasks': 0, 'pending_tasks': 0}
        try:
            cases = self.client.get('/cases/', params={'created_by': str(user_id)})
            stats['total_cases'] = cases.get('total', len(cases)) if not isinstance(cases, list) else len(cases)
        except:
            pass
        try:
            tasks = self.client.get('/tasks/', params={'assigned_to': str(user_id)})
            tasks_list = tasks if isinstance(tasks, list) else tasks.get('items', [])
            stats['total_tasks'] = tasks.get('total', len(tasks_list)) if not isinstance(tasks, list) else len(tasks_list)
            stats['completed_tasks'] = sum(1 for t in tasks_list if t.get('status') == 'completed')
            stats['pending_tasks'] = stats['total_tasks'] - stats['completed_tasks']
        except:
            pass
        return stats
