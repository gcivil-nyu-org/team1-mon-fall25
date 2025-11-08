# tickets/urls.py
from django.urls import path
from . import views

app_name = "tickets"

urlpatterns = [
    # Home / index
    path("", views.index, name="index"),
    # Ticket details
    # Keep old name "details" for existing code/templates,
    # and also add the name "ticket_details" for tests.
    path("details/<int:id>", views.details, name="details"),
    path("details/<int:id>", views.details, name="ticket_details"),
    # Ticket list
    path("list", views.ticket_list, name="ticket_list"),
    # Payment confirm API endpoint
    path("payment/confirm/", views.payment_confirm, name="payment_confirm"),
    # Thank-you + resend flows 
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
