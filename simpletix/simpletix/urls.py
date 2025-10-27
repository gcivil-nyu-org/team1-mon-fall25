from django.urls import path

from . import views

app_name = "simpletix"
urlpatterns = [
    path("", views.index, name="index"),
    path("webpage/<str:keyword>", views.webpage, name="webpage"),  # placeholder webpage
]
