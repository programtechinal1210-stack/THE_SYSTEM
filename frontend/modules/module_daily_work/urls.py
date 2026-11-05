from django.urls import path
from .views import index, reporting

app_name = 'daily_work'
urlpatterns = [path('', index, name='index'), path('report/', reporting, name='report')]
