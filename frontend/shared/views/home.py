from django.shortcuts import redirect


def home(request):
    return redirect("core_home")