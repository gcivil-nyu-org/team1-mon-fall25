import pytest
from django.urls import reverse
from orders.models import Order, BillingInfo
from tickets.models import Ticket


pytestmark = pytest.mark.django_db


def test_order_view_get_request(
    logged_in_attendee_client,
    order_url,
    ticket_info_vip,
    ticket_info_ga,
    ticket_info_soldout,
):
    """
    Test GET request:
    - Renders the correct template.
    - Form's ticket_info queryset is correctly filtered (excludes sold-out).
    """
    response = logged_in_attendee_client.get(order_url)

    assert response.status_code == 200
    assert "orders/order.html" in [t.name for t in response.templates]
    assert "form" in response.context
    assert "event" in response.context

    # Check that the form's queryset is correctly filtered
    form = response.context["form"]
    form_queryset = form.fields["ticket_info"].queryset

    assert form_queryset.count() == 2  # VIP and GA
    assert ticket_info_vip in form_queryset
    assert ticket_info_ga in form_queryset
    assert ticket_info_soldout not in form_queryset


@pytest.mark.parametrize(
    "client_fixture_name, data, expected_is_linked",
    [
        (
            # Case 1: User is logged in as "attendee"
            "logged_in_attendee_client",
            {
                "full_name": "Test Attendee Submit",
                "email": "attendee@example.com",
                "phone": "111-222-3333",
            },
            True,  # Expect order.attendee to be linked
        ),
        (
            # Case 2: User is a guest (not logged in or no role)
            "client",
            {
                "full_name": "Guest User Submit",
                "email": "guest@example.com",
                "phone": "444-555-6666",
            },
            False,  # Expect order.attendee to be None
        ),
    ],
)
def test_order_view_post_success(
    request,  # Pytest fixture to dynamically get other fixtures
    order_url,
    ticket_info_ga,
    attendee_profile,
    client_fixture_name,
    data,
    expected_is_linked,
):
    """
    Tests successful POST for both 'attendee' and 'guest' users.
    - Checks that an order is created.
    - Checks that availability is decremented.
    - Checks that order.attendee is linked (or not) based on session.
    """
    # Get the correct client (either basic 'client' or 'logged_in_attendee_client')
    client = request.getfixturevalue(client_fixture_name)

    # Add the ticket_info to the data payload
    data["ticket_info"] = ticket_info_ga.pk

    initial_availability = ticket_info_ga.availability
    initial_order_count = Order.objects.count()

    response = client.post(order_url, data)

    # Check order was created
    assert Order.objects.count() == initial_order_count + 1
    order = Order.objects.latest("id")

    # Check redirect to payment
    assert response.status_code == 302
    assert response.url == reverse("orders:process_payment", args=[order.id])

    # Check order details
    assert order.ticket_info == ticket_info_ga
    assert order.full_name == data["full_name"]

    # Check if attendee was linked correctly based on the 'desired_role' session
    if expected_is_linked:
        assert order.attendee == attendee_profile
    else:
        assert order.attendee is None

    # Check availability decrement
    ticket_info_ga.refresh_from_db()
    assert ticket_info_ga.availability == initial_availability - 1


# --- View: process_payment ---


def test_process_payment_success(logged_in_attendee_client, pending_order, mock_stripe):
    """Tests the successful creation of a Stripe checkout session."""
    url = reverse("orders:process_payment", args=[pending_order.id])
    response = logged_in_attendee_client.get(url)

    # Check for redirect to Stripe
    assert response.status_code == 302
    assert response.url == "https://stripe.com/mock_payment_url"

    # Check order was updated with session ID
    pending_order.refresh_from_db()
    assert pending_order.stripe_session_id == "sess_12345ABC"

    # Check Stripe API was called correctly
    mock_stripe.checkout.Session.create.assert_called_once()
    call_args = mock_stripe.checkout.Session.create.call_args[1]
    assert call_args["mode"] == "payment"
    assert call_args["metadata"]["order_id"] == pending_order.id
    expected_price = int(pending_order.ticket_info.price * 100)
    assert call_args["line_items"][0]["price_data"]["unit_amount"] == expected_price


# --- View: payment_success ---


def test_payment_success_view(logged_in_attendee_client, pending_order):
    """Tests the simple 'payment success' info page."""
    url = reverse("orders:payment_success", args=[pending_order.id])
    response = logged_in_attendee_client.get(url)

    assert response.status_code == 200
    assert "orders/payment_success.html" in [t.name for t in response.templates]
    assert response.context["order"] == pending_order


# --- View: payment_cancel ---


def test_payment_cancel_view(logged_in_attendee_client, pending_order):
    """
    Tests the 'payment cancel' page, which should also fail the order
    and restock the ticket.
    """
    ticket_info = pending_order.ticket_info
    initial_availability = ticket_info.availability
    assert pending_order.status == "pending"

    url = reverse("orders:payment_cancel", args=[pending_order.id])
    response = logged_in_attendee_client.get(url)

    assert response.status_code == 200
    assert "orders/payment_cancel.html" in [t.name for t in response.templates]

    # Check that the order was failed and ticket restocked
    pending_order.refresh_from_db()
    assert pending_order.status == "failed"
    ticket_info.refresh_from_db()
    assert ticket_info.availability == initial_availability + 1


# --- View: stripe_webhook ---

def post_webhook(client, webhook_url, payload, sig="sig_123"):
    """Helper function to post to the webhook."""
    return client.post(
        webhook_url,
        data=payload,
        content_type="application/json",
        HTTP_STRIPE_SIGNATURE=sig,
    )
    
def test_webhook_session_completed_paid(
    client, webhook_url, mock_stripe, pending_order
):
    """Tests successful fulfillment via webhook for 'checkout.session.completed'."""
    mock_event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "sess_123",
                "metadata": {"order_id": pending_order.id},
                "payment_status": "paid",
                "customer_details": {
                    "name": "Billing Name",
                    "email": "billing@example.com",
                    "phone": "9876543210",
                },
            }
        },
    }
    mock_stripe.Webhook.construct_event.return_value = mock_event

    assert Ticket.objects.count() == 0
    assert BillingInfo.objects.count() == 0

    response = post_webhook(client, webhook_url, mock_event)

    assert response.status_code == 200

    # Verify order fulfillment
    pending_order.refresh_from_db()
    assert pending_order.status == "completed"
    assert Ticket.objects.count() == 1
    assert BillingInfo.objects.count() == 1

    # Verify Ticket and BillingInfo
    ticket = Ticket.objects.first()
    assert ticket.ticketInfo == pending_order.ticket_info
    assert ticket.full_name == pending_order.full_name

    billing_info = BillingInfo.objects.first()
    assert billing_info.full_name == "Billing Name"
    assert pending_order.billing_info == billing_info

def test_webhook_session_expired(client, webhook_url, mock_stripe, pending_order):
    """Tests the webhook handler for an expired session."""
    mock_event = {
        "type": "checkout.session.expired",
        "data": {
            "object": {
                "id": "sess_123",
                "metadata": {"order_id": pending_order.id},
            }
        },
    }
    mock_stripe.Webhook.construct_event.return_value = mock_event
    ticket_info = pending_order.ticket_info
    initial_availability = ticket_info.availability

    response = post_webhook(client, webhook_url, mock_event)

    assert response.status_code == 200
    
    # Order should be failed and ticket restocked
    pending_order.refresh_from_db()
    assert pending_order.status == "failed"
    ticket_info.refresh_from_db()
    assert ticket_info.availability == initial_availability + 1