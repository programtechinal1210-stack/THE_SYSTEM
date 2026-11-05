# modules/module_notifications/views/ajax_list.py
from django.shortcuts import render
from django.http import JsonResponse
from data.arrays import NOTIFICATIONS

def ajax_notifications_list(request):
    user_id = request.session.get("user_id")
    page = int(request.GET.get("page", 1))
    size = int(request.GET.get("size", 10))
    
    notifications = [n for n in NOTIFICATIONS if n.get("user_id") == user_id]
    notifications = sorted(notifications, key=lambda x: x.get("created_at", ""), reverse=True)
    
    start = (page - 1) * size
    paginated = notifications[start:start+size]
    
    if request.headers.get("HX-Request"):
        return render(request, "notifications/partials/_notification.html", {"notifications": paginated})
    
    return JsonResponse({"notifications": paginated, "total": len(notifications), "page": page})
