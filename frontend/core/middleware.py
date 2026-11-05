from django.shortcuts import redirect
from core.request_context import current_request


class AuthMiddleware:
    PUBLIC_PREFIXES = ("/auth/", "/static/", "/health/")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        context = current_request.set(request)
        try:
            if (not request.path.startswith(self.PUBLIC_PREFIXES)
                    and not request.session.get("access_token")):
                return redirect("auth:login")
            return self.get_response(request)
        finally:
            current_request.reset(context)
