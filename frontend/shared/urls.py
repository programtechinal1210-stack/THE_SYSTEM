# shared/urls.py
from django.urls import path
from .views.home import home
from .views.search import search

app_name = "shared"

urlpatterns = [
    path("", home, name="home"),
    path("search/", search, name="search"),
]
