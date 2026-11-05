# core/views.py
from django.shortcuts import render, redirect
from django.http import HttpResponse


def home(request):
    """Neutral landing page for the reusable institutional Core."""
    if not (
        request.session.get("is_authenticated")
        or request.session.get("access_token")
    ):
        return redirect("auth:login")

    return render(
        request,
        "core/home.html",
        {
            "page_title": "النواة المؤسسية",
            "active": "core_home",
            "user_full_name": request.session.get("full_name", "مستخدم"),
            "show_welcome": request.session.pop("show_welcome", False),
        },
    )


def health_check(request):
    return HttpResponse("OK", content_type="text/plain")


def handler_404(request, exception):
    return render(request, "errors/404.html", status=404)


def handler_500(request):
    return render(request, "errors/500.html", status=500)


def handler_403(request, exception):
    return render(request, "errors/403.html", status=403)