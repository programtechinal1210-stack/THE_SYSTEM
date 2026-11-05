# modules/module_notifications/views/list.py
from django.shortcuts import render
from data.arrays import NOTIFICATIONS

def notifications_list(request):
    user_id = request.session.get("user_id")
    is_read = request.GET.get("is_read")
    
    notifications = [n for n in NOTIFICATIONS if n.get("user_id") == user_id]
    if is_read == "true": notifications = [n for n in notifications if n.get("is_read")]
    elif is_read == "false": notifications = [n for n in notifications if not n.get("is_read")]
    
    notifications = sorted(notifications, key=lambda x: x.get("created_at", ""), reverse=True)
    unread_count = len([n for n in notifications if not n.get("is_read")])
    
    return render(request, "notifications/list.html", {
        "notifications": notifications, "total": len(notifications),
        "unread_count": unread_count, "filters": {"is_read": is_read}
    })
