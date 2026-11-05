# shared/views/error.py
from django.shortcuts import render

def handler_404(request, exception):
    return render(request, 'errors/404.html', status=404)

def handler_500(request):
    return render(request, 'errors/500.html', status=500)

def handler_403(request, exception):
    return render(request, 'errors/403.html', status=403)
