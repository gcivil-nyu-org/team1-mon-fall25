import pytest

from events.models import Event
from tickets.models import TicketInfo, Ticket
from accounts.models import OrganizerProfile, UserProfile

from django.contrib.auth.models import User
from django.db.utils import IntegrityError
from decimal import Decimal
from django.utils import timezone

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


def test_ticketinfo_str_uses_event_title(ticket_info_ga):
    """
    __str__ should include the event title and category.
    """
    expected = f"{ticket_info_ga.event.title} - {ticket_info_ga.category}"
    assert str(ticket_info_ga) == expected


def test_ticket_str_with_event_and_attendee(ticket_info_ga, attendee_profile):
    """
    When ticketInfo, event title, category, and attendee user are present,
    __str__ should include all of them.
    """
    ticket = Ticket.objects.create(
        ticketInfo=ticket_info_ga,
        attendee=attendee_profile,
        full_name="Test User",
        email="test@example.com",
    )

    s = str(ticket)

    # Always starts with Ticket #<id>
    assert f"Ticket #{ticket.pk}" in s
    # Includes event title
    assert ticket_info_ga.event.title in s
    # Includes category in parentheses
    assert f"({ticket_info_ga.category})" in s
    # Includes attendee's user string
    assert str(attendee_profile.user) in s


def test_ticket_str_without_event_title(
    ticket_info_ga, attendee_profile, django_db_blocker
):
    """
    If event.title is blank/falsey, the 'for <title>' piece should be skipped
    but the category should still appear.
    """
    event = ticket_info_ga.event

    # Temporarily blank out the title, but keep the same event object
    original_title = event.title
    event.title = ""
    event.save()

    ticket = Ticket.objects.create(
        ticketInfo=ticket_info_ga,
        attendee=attendee_profile,
    )

    s = str(ticket)

    # No "for <title>" part because title is empty
    assert "for " not in s
    # Category still appears
    assert f"({ticket_info_ga.category})" in s

    # Restore title so we don't affect other tests
    event.title = original_title
    event.save()


def test_ticket_str_minimal_ticket():
    """
    If there is no ticketInfo and no attendee, __str__ should gracefully
    fall back to 'Ticket #<id>' with no extra pieces.
    """
    ticket = Ticket.objects.create(
        full_name="Lonely Ticket",
        email="lonely@example.com",
    )

    assert str(ticket) == f"Ticket #{ticket.pk}"


def test_ensure_qr_generates_and_is_idempotent(ticket_info_ga):
    """
    ensure_qr should generate a QR code only if missing, and should not
    overwrite an existing qr_code if called again. It does NOT save by itself.
    """
    ticket = Ticket.objects.create(
        ticketInfo=ticket_info_ga,
        full_name="QR User",
        email="qr@example.com",
    )

    # Initially no qr_code in memory / DB
    assert ticket.qr_code is None

    # First call generates the code (in memory)
    ticket.ensure_qr()
    assert ticket.qr_code is not None
    first_code = ticket.qr_code
    assert first_code.startswith("TCKT-")

    # Second call should NOT change the existing code
    ticket.ensure_qr()
    assert ticket.qr_code == first_code

    # Once we save, the code should be persisted to the DB
    ticket.save()
    ticket.refresh_from_db()
    assert ticket.qr_code == first_code
