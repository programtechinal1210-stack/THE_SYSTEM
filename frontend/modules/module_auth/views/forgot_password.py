from django.http import HttpResponse

def forgot_password_view(request, *args, **kwargs):
    return HttpResponse("Contact your institution administrator to reset your password.", status=501)
