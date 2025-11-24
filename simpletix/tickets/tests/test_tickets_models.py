import pytest
from django.contrib.auth.models import User
from django.db.utils import IntegrityError
from decimal import Decimal
from django.utils import timezone

from events.models import Event
from accounts.models import OrganizerProfile, UserProfile
from tickets.models import TicketInfo, Ticket

pytestmark = pytest.mark.django_db


@pytest.fixture
def organizer_user():
    """Fixture for the organizer user."""
    return User.objects.create_user(username="organizeruser", password="Passw0rd1!")


@pytest.fixture
def attendee_user():
    """Fixture for the attendee user."""
    return User.objects.create_user(username="attendeeuser", password="Passw0rd1!")


@pytest.fixture
def organizer_profile(organizer_user):
    """Fixture for the organizer profile."""
    profile, _ = OrganizerProfile.objects.get_or_create(user=organizer_user)
    return profile


@pytest.fixture
def attendee_profile(attendee_user):
    """Fixture for the attendee profile."""
    profile, _ = UserProfile.objects.get_or_create(user=attendee_user)
    return profile


@pytest.fixture
def test_event(organizer_profile):
    """Fixture for a standard test event."""
    return Event.objects.create(
        organizer=organizer_profile,
        title="Test Event",
        date=timezone.now().date(),
        time=timezone.now().time(),
    )


@pytest.fixture
def another_test_event(organizer_profile):
    """Fixture for a second test event used in TicketModel tests."""
    return Event.objects.create(
        organizer=organizer_profile,
        title="Another Test Event",
        date=timezone.now().date(),
        time=timezone.now().time(),
    )


@pytest.fixture
def ticket_info_ga(another_test_event):
    """Fixture for General Admission TicketInfo."""
    return TicketInfo.objects.create(
        event=another_test_event,
        category="General Admission",
        price=Decimal("30.00"),
        availability=50,
    )


# --- models:TicketInfo ---


def test_create_ticket_info(organizer_profile, test_event):
    """Test creating a TicketInfo instance."""
    ticket_info = TicketInfo.objects.create(
        organizer=organizer_profile,
        event=test_event,
        category="General Admission",
        price=Decimal("25.00"),
        availability=100,
    )
    assert ticket_info.organizer == organizer_profile
    assert ticket_info.event == test_event
    assert ticket_info.category == "General Admission"
    assert ticket_info.price == Decimal("25.00")
    assert ticket_info.availability == 100


def test_ticket_info_defaults(test_event):
    """Test default values for price and availability."""
    ticket_info = TicketInfo.objects.create(event=test_event, category="Early Bird")
    assert ticket_info.price == Decimal("0.00")
    assert ticket_info.availability == 0


def test_ticket_info_unique_together(test_event):
    """Test the unique_together constraint for event and category."""
    # Create the first ticket info
    TicketInfo.objects.create(
        event=test_event,
        category="General Admission",
        price=Decimal("10.00"),  # Use Decimal
    )
    # Attempt to create another with the same event and category
    with pytest.raises(IntegrityError):
        TicketInfo.objects.create(
            event=test_event,
            category="General Admission",  # Same category
            price=Decimal("15.00"),
        )


# --- models:Ticket ---


def test_create_ticket(attendee_profile, ticket_info_ga):
    """Test creating a Ticket instance."""
    ticket = Ticket.objects.create(
        attendee=attendee_profile,
        ticketInfo=ticket_info_ga,
        full_name="Test Attendee",
        email="test@example.com",
        phone="123-456-7890",
    )
    assert ticket.attendee == attendee_profile
    assert ticket.ticketInfo == ticket_info_ga
    assert ticket.full_name == "Test Attendee"
    assert ticket.email == "test@example.com"
    assert ticket.phone == "123-456-7890"


# --- TicketInfo ordering behaviour (bug #149 regression tests) ---


def test_ticket_info_ordering_is_alphabetical_by_category(test_event):
    """
    For a given event, TicketInfo entries should appear in alphabetical
    order by category, regardless of creation order.
    This protects the fix for:
    'Ticket Categories Shift Display Order' (Bug #149).
    """
    # Create in a non-alphabetical order
    TicketInfo.objects.create(
        event=test_event,
        category="VIP",
        price=Decimal("100.00"),
        availability=25,
    )
    TicketInfo.objects.create(
        event=test_event,
        category="General Admission",
        price=Decimal("50.00"),
        availability=50,
    )
    TicketInfo.objects.create(
        event=test_event,
        category="Early Bird",
        price=Decimal("35.00"),
        availability=15,
    )

    categories = list(test_event.ticketInfo.values_list("category", flat=True))

    # Expected stable alphabetical order
    assert categories == ["Early Bird", "General Admission", "VIP"]


def test_editing_ticket_info_does_not_change_display_order(test_event):
    """
    Editing a TicketInfo (e.g., changing availability/quantity) should
    not change the relative order of categories for an event.
    This matches the expected behaviour in the organizer edit event UI.
    """
    TicketInfo.objects.create(
        event=test_event,
        category="General Admission",
        price=Decimal("50.00"),
        availability=50,
    )
    vip = TicketInfo.objects.create(
        event=test_event,
        category="VIP",
        price=Decimal("100.00"),
        availability=25,
    )
    TicketInfo.objects.create(
        event=test_event,
        category="Early Bird",
        price=Decimal("35.00"),
        availability=15,
    )

    # Simulate the organizer editing just this ticket (like changing quantity)
    vip.availability = 99
    vip.save()

    categories = list(test_event.ticketInfo.values_list("category", flat=True))

    # Order should still be alphabetical, not "VIP last-edited goes to bottom"
    assert categories == ["Early Bird", "General Admission", "VIP"]
