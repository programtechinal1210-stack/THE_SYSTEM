# modules/module_notifications/views/base.py
from django.shortcuts import render, redirect
from django.contrib import messages
from data.arrays import NOTIFICATIONS, get_notification_by_id

class NotificationsBaseView:
    def __init__(self, request):
        self.request = request
    
    def render(self, template, context=None):
        return render(self.request, template, context or {})
    
    def redirect(self, url_name, *args, **kwargs):
        return redirect(url_name, *args, **kwargs)
    
    def add_message(self, level, message):
        messages.add_message(self.request, level, message)
    
    def get_notification(self, notif_id):
        return get_notification_by_id(notif_id)
    
    def get_user_notifications(self):
        user_id = self.request.session.get("user_id")
        return [n for n in NOTIFICATIONS if n.get("user_id") == user_id]
