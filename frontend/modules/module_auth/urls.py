# modules/module_auth/urls.py
from django.urls import path
from .views import login, logout, register, forgot_password, reset_password, mfa

app_name = "auth"

urlpatterns = [
    path("login/", login.login_view, name="login"),
    path("logout/", logout.logout_view, name="logout"),
    path("mfa/", mfa.mfa_view, name="mfa"),
    path("register/", register.register_view, name="register"),
    path("forgot-password/", forgot_password.forgot_password_view, name="forgot_password"),
    path("reset-password/<uidb64>/<token>/", reset_password.reset_password_view, name="reset_password"),
]
