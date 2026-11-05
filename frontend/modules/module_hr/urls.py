from django.urls import path

from .views import employee_detail, home

app_name = "hr"
urlpatterns = [
    path("", home, name="home"),
    path("employees/<str:employee_id>/", employee_detail, name="employee_detail"),
]
