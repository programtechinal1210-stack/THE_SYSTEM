from django.http import HttpResponseForbidden

def register_view(request):
    return HttpResponseForbidden("Account creation is managed by the institution administrator.")
