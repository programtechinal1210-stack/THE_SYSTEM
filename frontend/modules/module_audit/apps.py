from django.apps import AppConfig


class ModuleAuditConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'modules.module_audit'
    verbose_name = 'التدقيق والمتابعة'
    verbose_name_plural = 'التدقيق والمتابعة'
    
    # أيقونة القائمة الجانبية
    menu_icon = 'fas fa-shield-alt'
    
    # الترتيب في القائمة
    menu_order = 7
    
    def ready(self):
        pass
