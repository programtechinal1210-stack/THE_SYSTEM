# modules/module_auth/apps.py
from django.apps import AppConfig

class ModuleAuthConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "modules.module_auth"
    verbose_name = "المصادقة"
