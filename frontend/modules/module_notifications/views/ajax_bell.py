# modules/module_notifications/views/ajax_bell.py
from django.shortcuts import render
from django.http import JsonResponse
from data.arrays import NOTIFICATIONS

def ajax_notification_bell(request):
    user_id = request.session.get("user_id")
    user_notifications = [n for n in NOTIFICATIONS if n.get("user_id") == user_id]
    unread = [n for n in user_notifications if not n.get("is_read")]
    recent = sorted(user_notifications, key=lambda x: x.get("created_at", ""), reverse=True)[:5]
    
    if request.headers.get("HX-Request"):
        return render(request, "notifications/partials/_dropdown_list.html", {
            "notifications": recent, "unread_count": len(unread)
        })
    
    return JsonResponse({"notifications": recent, "unread_count": len(unread), "total": len(user_notifications)})
