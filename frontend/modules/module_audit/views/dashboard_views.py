from django.shortcuts import render
from django.http import JsonResponse
from ..services.audit_api import (
    get_audit_logs, get_audit_summary, get_followups,
    get_execution, get_anomalies, get_alerts, get_exports
)


def index(request):
    return render(request, "audit/index.html")


def api_stats(request):
    try:
        data = get_audit_summary(request)
        return JsonResponse(data)
    except:
        return JsonResponse({"total_actions": 0, "unique_users": 0, "pending_followups": 0, "open_anomalies": 0})


def tab_dashboard(request):
    return render(request, "audit/partials/_stats_cards.html")


def tab_logs(request):
    data = get_audit_logs(request)
    return render(request, "audit/partials/_audit_table.html", {"logs": data.get("results", [])})


def tab_followups(request):
    data = get_followups(request)
    return render(request, "audit/partials/_followup_table.html", {"followups": data.get("results", [])})


def tab_execution(request):
    data = get_execution(request)
    return render(request, "audit/partials/_execution_table.html", {"executions": data.get("results", [])})


def tab_anomalies(request):
    data = get_anomalies(request)
    return render(request, "audit/partials/_anomaly_list.html", {"anomalies": data.get("results", [])})


def tab_alerts(request):
    data = get_alerts(request)
    return render(request, "audit/partials/_alert_list.html", {"alerts": data.get("results", [])})


def tab_exports(request):
    data = get_exports(request)
    exports = data.get("results", [])
    if exports:
        return render(request, "audit/partials/_export_table.html", {"exports": exports})
    return render(request, "audit/partials/_empty_state.html", {
        "title": "التصدير", "message": "لا توجد عمليات تصدير"
    })
