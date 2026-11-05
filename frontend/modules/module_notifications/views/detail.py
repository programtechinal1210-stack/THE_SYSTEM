# modules/module_notifications/views/detail.py
from django.shortcuts import render, redirect
from django.contrib import messages
from data.arrays import get_notification_by_id, now

def notifications_detail(request, notif_id):
    notification = get_notification_by_id(notif_id)
    if not notification:
        messages.error(request, "الإشعار غير موجود")
        return redirect("notifications:list")
    
    if not notification.get("is_read"):
        notification["is_read"] = True
        notification["read_at"] = now()
    
    return render(request, "notifications/detail.html", {"notification": notification})
