# modules/module_users/apps.py
from django.apps import AppConfig

class ModuleUsersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "modules.module_users"
    verbose_name = "المستخدمين"
