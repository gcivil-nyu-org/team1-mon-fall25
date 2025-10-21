from django.urls import path

from . import views

app_name = "tickets"
urlpatterns = [
    path("", views.index, name="index"),
    path("<int:id>", views.order, name="order"),
    path("details/<int:id>", views.details, name="ticket_details"),
    path("list", views.ticket_list, name="ticket_list")
]
