# shared/views/base.py
from django.shortcuts import render
from data.arrays import NOTIFICATIONS

def get_notifications(request):
    if request.user.is_authenticated:
        user_notifications = [n for n in NOTIFICATIONS if n.get('user_id') == str(request.user.id)]
        return {'notifications': user_notifications[:5], 'unread_count': len([n for n in user_notifications if not n.get('is_read')])}
    return {'notifications': [], 'unread_count': 0}
