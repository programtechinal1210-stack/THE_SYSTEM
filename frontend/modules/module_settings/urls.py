from django.urls import path, re_path
from .views import settings as settings_views
from .views import settings_views as api_views
from .views import notification_views as notif_views

app_name = "settings"

urlpatterns = [
    path("", settings_views.settings_index, name="index"),
    path("api/get/", api_views.get_settings_api, name="api_get_settings"),
    path("api/save/", api_views.save_settings_api, name="api_save_settings"),
    path("api/user/save/", api_views.save_user_settings_api, name="api_save_user_settings"),
    path("api/change-password/", api_views.change_password_api, name="api_change_password"),
    path("api/notifications/", notif_views.get_notifications_api, name="api_notifications"),
    path("api/notifications/count/", notif_views.get_unread_count_api, name="api_notifications_count"),
    path("api/notifications/read/<str:notification_id>/", notif_views.mark_read_api, name="api_notifications_read"),
    path("api/notifications/read-all/", notif_views.mark_all_read_api, name="api_notifications_read_all"),
    path("api/notifications/types/", notif_views.get_notification_types_api, name="api_notifications_types"),
    path("api/users/list/", notif_views.get_users_api, name="api_users_list"),
]
