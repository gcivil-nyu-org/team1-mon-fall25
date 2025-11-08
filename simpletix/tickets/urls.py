from django.urls import path

from . import views

app_name = "tickets"

urlpatterns = [
    path("", views.index, name="index"),
    path("details/<int:id>/", views.details, name="ticket_details"),
    path("list", views.ticket_list, name="ticket_list"),
    # Used by tests for the JSON-based ticket issuance endpoint
    path("payment-confirm/", views.payment_confirm, name="payment_confirm"),
    # Thank-you page keyed by order_id (can be non-numeric, e.g. "order-no-email")
    path(
        "thank-you/<str:order_id>/",
        views.ticket_thank_you,
        name="ticket_thank_you",
    ),
    # Re-send tickets, also keyed by order_id (string)
    path(
        "resend/<str:order_id>/",
        views.ticket_resend,
        name="ticket_resend",
    ),
]
