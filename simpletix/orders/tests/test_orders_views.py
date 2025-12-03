import pytest
from unittest.mock import MagicMock
import stripe
import os

from django.urls import reverse
from django.core import mail
from orders.forms import OrderForm
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
                "quantity": "10",
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
                "quantity": "10",
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
    order = Order.objects.latest("id")
    assert Order.objects.count() == initial_order_count + 1

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
    assert ticket_info_ga.availability == initial_availability - order.quantity


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


def test_process_payment_stripe_api_error(
    logged_in_attendee_client, pending_order, mock_stripe
):
    """Tests the error handling when Stripe API fails."""
    # Simulate a Stripe API exception
    mock_stripe.checkout.Session.create.side_effect = stripe._error.StripeError(
        "API Connection Error"
    )

    ticket_info = pending_order.ticket_info
    initial_availability = ticket_info.availability

    url = reverse("orders:process_payment", args=[pending_order.id])
    response = logged_in_attendee_client.get(url)

    # Should redirect to cancel page
    assert response.status_code == 302
    assert response.url == reverse("orders:payment_cancel", args=[pending_order.id])

    # Order should be marked as 'failed' and ticket restocked
    pending_order.refresh_from_db()
    assert pending_order.status == "failed"
    ticket_info.refresh_from_db()
    assert ticket_info.availability == initial_availability + pending_order.quantity


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
    assert ticket_info.availability == initial_availability + pending_order.quantity


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
                "metadata": {
                    "order_id": pending_order.id,
                    "environment": os.getenv("ENVIRONMENT"),
                },
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
    assert Ticket.objects.count() == pending_order.quantity
    assert BillingInfo.objects.count() == 1

    # Verify Ticket and BillingInfo
    ticket = Ticket.objects.first()
    assert ticket.ticketInfo == pending_order.ticket_info
    assert ticket.full_name == pending_order.full_name

    billing_info = BillingInfo.objects.first()
    assert billing_info.full_name == "Billing Name"
    assert pending_order.billing_info == billing_info


def test_webhook_session_completed_not_paid(
    client, webhook_url, mock_stripe, pending_order
):
    """Tests webhook for a completed session that was NOT paid."""
    mock_event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "sess_123",
                "metadata": {
                    "order_id": pending_order.id,
                    "environment": os.getenv("ENVIRONMENT"),
                },
                "payment_status": "unpaid",  # <-- Not paid
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
    assert Ticket.objects.count() == 0
    ticket_info.refresh_from_db()
    assert ticket_info.availability == initial_availability + pending_order.quantity


def test_webhook_session_expired(client, webhook_url, mock_stripe, pending_order):
    """Tests the webhook handler for an expired session."""
    mock_event = {
        "type": "checkout.session.expired",
        "data": {
            "object": {
                "id": "sess_123",
                "metadata": {
                    "order_id": pending_order.id,
                    "environment": os.getenv("ENVIRONMENT"),
                },
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
    assert ticket_info.availability == initial_availability + pending_order.quantity


def test_webhook_unhandled_event(client, webhook_url, mock_stripe):
    """Tests that other events are received but not acted upon."""
    mock_event = {
        "type": "payment_intent.succeeded",
        "data": {
            "object": {
                "metadata": {
                    "environment": os.getenv("ENVIRONMENT"),
                }
            }
        },
    }
    mock_stripe.Webhook.construct_event.return_value = mock_event

    response = post_webhook(client, webhook_url, mock_event)
    assert response.status_code == 200


def test_webhook_handler_order_not_found(client, webhook_url, mock_stripe):
    """Tests that the handler safely exits if the order ID is invalid."""
    mock_event = {
        "type": "checkout.session.expired",
        "data": {
            "object": {
                "id": "sess_123",
                "metadata": {
                    "order_id": 99999,
                    "environment": os.getenv("ENVIRONMENT"),
                },  # <-- Fake ID
            }
        },
    }
    mock_stripe.Webhook.construct_event.return_value = mock_event

    response = post_webhook(client, webhook_url, mock_event)
    # Should not crash, just prints an error and returns 200
    assert response.status_code == 200


def test_webhook_handler_env_not_found(client, webhook_url, mock_stripe, pending_order):
    """Tests that the handler safely exits if the order ID is invalid."""
    mock_event = {
        "type": "checkout.session.expired",
        "data": {
            "object": {
                "id": "sess_123",
                "metadata": {
                    "order_id": pending_order.id,
                    "environment": "other_env",
                },  # <-- Fake ID
            }
        },
    }
    mock_stripe.Webhook.construct_event.return_value = mock_event

    response = post_webhook(client, webhook_url, mock_event)
    # Should not crash, just prints an error and returns 200
    assert response.status_code == 200


def test_order_view_get_preselect_valid_ticket(
    logged_in_attendee_client, test_event, ticket_info_vip, ticket_info_ga
):
    """
    If a valid ticket_category_id is provided in GET params, it should
    preselect that ticket in the form.
    """
    url = reverse("orders:order", args=[test_event.id])
    url += f"?ticket_category_id={ticket_info_vip.id}"

    response = logged_in_attendee_client.get(url)

    assert response.status_code == 200
    form = response.context["form"]
    assert isinstance(form, OrderForm)

    # The correct ticket is preselected
    assert form.initial["ticket_info"] == ticket_info_vip.id
    assert form.fields["quantity"].widget.attrs["max"] == ticket_info_vip.availability
    assert form.fields["quantity"].max_value == ticket_info_vip.availability


def test_order_view_get_preselect_invalid_ticket(
    logged_in_attendee_client, test_event, ticket_info_vip, ticket_info_ga
):
    """
    If an invalid ticket_category_id is provided, the form should fall
    back to the first available ticket.
    """
    invalid_id = 9999
    url = reverse("orders:order", args=[test_event.id])
    url += f"?ticket_category_id={invalid_id}"

    response = logged_in_attendee_client.get(url)
    assert response.status_code == 200

    form = response.context["form"]
    first_ticket = form.fields["ticket_info"].queryset.first()

    # No initial preselection
    assert form.initial.get("ticket_info") is None

    # Quantity max falls back to the first available ticket
    assert form.fields["quantity"].widget.attrs["max"] == first_ticket.availability
    assert form.fields["quantity"].max_value == first_ticket.availability


def test_order_view_get_preselect_sold_out_ticket(
    logged_in_attendee_client, test_event, ticket_info_vip, ticket_info_soldout
):
    """
    A sold-out ticket in ticket_category_id param should not be preselected.
    """
    url = reverse("orders:order", args=[test_event.id])
    url += f"?ticket_category_id={ticket_info_soldout.id}"

    response = logged_in_attendee_client.get(url)
    assert response.status_code == 200

    form = response.context["form"]
    # Sold-out ticket should not be in the queryset, so no initial selection
    assert form.initial.get("ticket_info") is None

    # Quantity max falls back to first available ticket
    first_ticket = form.fields["ticket_info"].queryset.first()
    assert form.fields["quantity"].widget.attrs["max"] == first_ticket.availability
    assert form.fields["quantity"].max_value == first_ticket.availability


def test_order_view_ticket_availability_data(
    logged_in_attendee_client, test_event, ticket_info_vip, ticket_info_ga
):
    """
    Context should include ticket_availability_data mapping ticket IDs to availability.
    """
    url = reverse("orders:order", args=[test_event.id])
    response = logged_in_attendee_client.get(url)

    expected_data = {
        str(ticket_info_vip.id): ticket_info_vip.availability,
        str(ticket_info_ga.id): ticket_info_ga.availability,
    }

    assert response.context["ticket_availability_data"] == expected_data


def test_webhook_refund_succeeded_sends_email(
    client, webhook_url, mock_stripe, pending_order
):
    """
    Tests that a successful refund webhook updates the order status
    and triggers the send_refund_email service.
    """
    # 1. Setup: Move order to 'completed' state so it's eligible for refund
    pending_order.status = "completed"
    pending_order.save()

    # Calculate full refund amount in cents
    refund_amount_cents = int(pending_order.total_price * 100)

    # 2. Mock the Stripe Refund Event
    mock_event = {
        "type": "refund.updated",
        "data": {
            "object": {
                "id": "sess_123",
                "amount": refund_amount_cents,
                "status": "succeeded",
                "metadata": {
                    "order_id": pending_order.id,
                    "environment": os.getenv("ENVIRONMENT"),
                },
            }
        },
    }
    mock_stripe.Webhook.construct_event.return_value = mock_event

    # 3. Clear outbox and fire webhook
    mail.outbox = []
    response = post_webhook(client, webhook_url, mock_event)

    assert response.status_code == 200

    # 4. Verify Order Status Update
    pending_order.refresh_from_db()
    assert pending_order.status == "refunded"
    assert pending_order.amount_refunded == pending_order.total_price

    # 5. Verify Email was Sent
    assert len(mail.outbox) == 1
    email = mail.outbox[0]

    # Check Subject
    assert "Full Refund Notification" in email.subject
    assert f"Order #{pending_order.id}" in email.subject

    # Check Body Content
    assert f"Refund Amount: ${pending_order.total_price:,.2f}" in email.body
    assert "SimpleTix Team" in email.body

    event = pending_order.ticket_info.event
    organizer = event.organizer

    # Check Event Info block
    assert "Event Information:" in email.body
    assert f"Event: {event.title}" in email.body
    assert f"Location: {event.location}" in email.body

    # Check Organizer Info block
    assert "Organizer Information:" in email.body
    organizer_name = organizer.full_name or organizer.user.username
    assert f"Name: {organizer_name}" in email.body


def test_refund_full_success(
    organizer_client, test_event, completed_order, mock_stripe
):
    """
    Test that 'refund_full' action calls Stripe API and updates status.
    """
    url = reverse("orders:event_order_list", args=[test_event.id])

    # Mock Session Retrieve (to get payment_intent)
    mock_session = MagicMock()
    mock_session.payment_intent = "pi_test_123"
    mock_stripe.checkout.Session.retrieve.return_value = mock_session

    data = {"action": "refund_full", "selected_orders": [completed_order.id]}

    response = organizer_client.post(url, data, follow=True)

    # 1. Check Stripe API call
    mock_stripe.Refund.create.assert_called_once()
    call_args = mock_stripe.Refund.create.call_args[1]
    assert call_args["payment_intent"] == "pi_test_123"
    assert call_args["reason"] == "requested_by_customer"

    # 2. Check Database Update
    completed_order.refresh_from_db()
    assert completed_order.status == "refund_processing"

    # 3. Check Message
    messages = list(response.context["messages"])
    assert len(messages) > 0
    assert "Refund is being processed" in str(messages[0])


def test_refund_partial_success(
    organizer_client, test_event, completed_order, mock_stripe
):
    """
    Test that 'refund_partial' calculates the correct amount and calls Stripe API.
    """
    url = reverse("orders:event_order_list", args=[test_event.id])

    # Setup Order: 2 tickets @ $50 each = $100 Total
    # (Fixture already sets price=50, quantity=2)

    # Mock Session
    mock_session = MagicMock()
    mock_session.payment_intent = "pi_test_123"
    mock_stripe.checkout.Session.retrieve.return_value = mock_session

    # Refund 50% ($50.00)
    data = {
        "action": "refund_partial",
        "selected_orders": [completed_order.id],
        "refund_percentage": "50",
    }

    organizer_client.post(url, data, follow=True)

    # 1. Check Stripe API call amount
    mock_stripe.Refund.create.assert_called_once()
    call_args = mock_stripe.Refund.create.call_args[1]

    # Expected: 50% of (50 * 2) = $50.00 = 5000 cents
    assert call_args["amount"] == 5000
    assert call_args["payment_intent"] == "pi_test_123"

    # 2. Check Database Update
    completed_order.refresh_from_db()
    assert completed_order.status == "refund_processing"
