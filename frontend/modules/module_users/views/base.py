# modules/module_users/views/base.py
from django.shortcuts import render, redirect
from django.contrib import messages
from shared.services.api_client import ApiClient, ApiException

class UsersBaseView:
    def __init__(self, request):
        self.request = request
        self.client = ApiClient()

    def render(self, template, context=None):
        return render(self.request, template, context or {})

    def redirect(self, url_name, *args, **kwargs):
        return redirect(url_name, *args, **kwargs)

    def add_message(self, level, message):
        messages.add_message(self.request, level, message)

    def get_user(self, user_id):
        try:
            return self.client.get(f'/users/{user_id}')
        except ApiException:
            return None

    def get_users(self, params=None):
        try:
            result = self.client.get('/users/', params=params or {})
            return result if isinstance(result, list) else result.get('items', [])
        except ApiException:
            return []
