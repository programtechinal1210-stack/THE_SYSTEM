from django.urls import path
from core import workspace
from .views import core_views as views

app_name = 'notifications'
urlpatterns = [
    path('', workspace.page, {'section': 'notifications'}, name='list'),
    path('read-all/', views.mark_all_read, name='mark_all_read'),
    path('read/<uuid:notif_id>/', views.mark_read, name='mark_read'),
    path('ajax/bell/', views.bell, name='ajax_bell'),
    path('ajax/list/', views.listing, name='ajax_list'),
    path('<uuid:notif_id>/', views.detail, name='detail'),
]
