# modules/module_notifications/views/mark_all_read.py
from django.shortcuts import redirect
from django.contrib import messages
from django.http import JsonResponse
from data.arrays import NOTIFICATIONS, now

def mark_all_read(request):
    user_id = request.session.get("user_id")
    for notification in NOTIFICATIONS:
        if notification.get("user_id") == user_id and not notification.get("is_read"):
            notification["is_read"] = True
            notification["read_at"] = now()
    
    if request.headers.get("HX-Request"):
        return JsonResponse({"success": True})
    
    messages.success(request, "تم تعليم جميع الإشعارات كمقروءة")
    return redirect("notifications:list")
