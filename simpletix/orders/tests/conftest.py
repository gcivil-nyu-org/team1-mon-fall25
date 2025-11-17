import pytest
from unittest.mock import patch, MagicMock
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone


from events.models import Event
from accounts.models import OrganizerProfile, UserProfile
from tickets.models import TicketInfo
from orders.models import Order, BillingInfo


# Mark all tests in this file as needing database access
pytestmark = pytest.mark.django_db


@pytest.fixture
def organizer_user(db):
    """Fixture for the organizer user."""
    return User.objects.create_user(username="org_viewer", password="Passw0rd1!")


@pytest.fixture
def attendee_user(db):
    """Fixture for the attendee user."""
    return User.objects.create_user(username="att_viewer", password="Passw0rd1!")


@pytest.fixture
def organizer_profile(db, organizer_user):
    """Fixture for the organizer profile."""
    profile, _ = OrganizerProfile.objects.get_or_create(user=organizer_user)
    return profile


@pytest.fixture
def attendee_profile(db, attendee_user):
    """Fixture for the attendee profile."""
    profile, _ = UserProfile.objects.get_or_create(user=attendee_user)
    return profile


@pytest.fixture
def test_event(db, organizer_profile):
    """Fixture for the event used in tests."""
    return Event.objects.create(
        organizer=organizer_profile,
        title="View Test Event",
        date=timezone.now().date(),
        time=timezone.now().time(),
    )


@pytest.fixture
def ticket_info_vip(db, test_event):
    """Fixture for VIP TicketInfo."""
    return TicketInfo.objects.create(
        event=test_event, category="VIP", price=100, availability=100
    )


@pytest.fixture
def ticket_info_ga(db, test_event):
    """Fixture for General Admission TicketInfo."""
    return TicketInfo.objects.create(
        event=test_event, category="General Admission", price=50, availability=500
    )


@pytest.fixture
def ticket_info_soldout(db, test_event):
    """Fixture for Sold Out TicketInfo."""
    return TicketInfo.objects.create(
        event=test_event, category="Early Bird", price=40, availability=0
    )


@pytest.fixture
def order_url(test_event):
    """Fixture for the order URL."""
    return reverse("orders:order", args=[test_event.id])


@pytest.fixture
def login_url():
    """Fixture for the login URL."""
    # Construct the URL with the role parameter for attendee
    base_url = reverse("accounts:login")
    return f"{base_url}?role=attendee"


@pytest.fixture
def logged_in_attendee_client(client, login_url, attendee_user):
    """Fixture for a client logged in as an attendee via the custom view."""
    login_data = {"username": attendee_user.username, "password": "Passw0rd1!"}
    # Log in using the actual login view POST
    client.post(login_url, login_data, follow=True)
    # Verify session is set correctly after login
    assert client.session.get("desired_role") == "attendee"
    return client


@pytest.fixture
def pending_order(db, ticket_info_ga, attendee_profile):
    """Fixture for a pending order, created by an attendee."""
    return Order.objects.create(
        attendee=attendee_profile,
        ticket_info=ticket_info_ga,
        quantity=10,
        full_name="Test User",
        email="test@example.com",
        phone="1234567890",
    )


@pytest.fixture
def mock_stripe():
    """Mocks the stripe API calls."""
    with patch("orders.views.stripe") as mock_stripe_module:
        # Mock the checkout session
        mock_session = MagicMock()
        mock_session.id = "sess_12345ABC"
        mock_session.url = "https://stripe.com/mock_payment_url"
        mock_stripe_module.checkout.Session.create.return_value = mock_session

        # Mock the webhook construction
        mock_stripe_module.Webhook.construct_event.return_value = {}
        yield mock_stripe_module


@pytest.fixture
def webhook_url():
    """Fixture for the webhook URL."""
    return reverse("orders:stripe_webhook")


@pytest.fixture
def billing_info(db):
    """Fixture for a sample BillingInfo object."""
    return BillingInfo.objects.create(
        full_name="Test Billing",
        email="billing@example.com",
        phone="123-456-7890",
    )


@pytest.fixture
def order(db, attendee_profile, ticket_info_ga, billing_info):
    """
    Fixture for an Order object linked to billing info.
    This fixture also implicitly tests the create part of the save() method.
    """
    return Order.objects.create(
        attendee=attendee_profile,
        ticket_info=ticket_info_ga,
        billing_info=billing_info,
        quantity=10,
        full_name="Test Order User",
        email="order@example.com",
    )
