from django.urls import path
from .views import home
from .configuration import page as configuration
from .operations import page as operations
from .requests import page as requests

app_name = 'inventory'
urlpatterns = [path('', home, name='home'), path('configuration/', configuration, name='configuration'),
               path('operations/', operations, name='operations'),path('requests/', requests, name='requests'),
               path('custody/',operations,{'mode_override':'custody'},name='custody')]
