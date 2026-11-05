# modules/module_notifications/views/mark_read.py
from django.shortcuts import redirect
from django.contrib import messages
from django.http import JsonResponse
from data.arrays import get_notification_by_id, now

def mark_notification_read(request, notif_id):
    notification = get_notification_by_id(notif_id)
    if notification:
        notification["is_read"] = True
        notification["read_at"] = now()
        if request.headers.get("HX-Request"):
            return JsonResponse({"success": True})
        messages.success(request, "تم تعليم الإشعار كمقروء")
    else:
        if request.headers.get("HX-Request"):
            return JsonResponse({"success": False, "error": "الإشعار غير موجود"})
        messages.error(request, "الإشعار غير موجود")
    
    return redirect("notifications:list")
