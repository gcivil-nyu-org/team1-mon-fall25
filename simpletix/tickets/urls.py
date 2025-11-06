from django.urls import path

from . import views

app_name = "tickets"
urlpatterns = [
    path("", views.index, name="index"),
    path("<int:id>", views.order, name="order"),
    path("details/<int:id>", views.details, name="ticket_details"),
    path("list", views.ticket_list, name="ticket_list"),
    path("payment/confirm/", views.payment_confirm, name="payment_confirm"),
    path(
        "thank-you/<str:order_id>/",
        views.ticket_thank_you,
        name="ticket_thank_you",
    ),
    path(
        "resend/<str:order_id>/",
        views.ticket_resend,
        name="ticket_resend",
    ),
]
