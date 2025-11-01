import pytest
from django.contrib.auth.models import User
from django.utils import timezone

from events.models import Event
from accounts.models import OrganizerProfile
from tickets.models import TicketInfo
from orders.forms import OrderForm

pytestmark = pytest.mark.django_db


# --- forms:OrderForm ---


@pytest.fixture
def test_user_order_org():
    """Fixture for the organizer user in OrderForm tests."""
    return User.objects.create_user(username="testorderorg", password="Passw0rd1!")


@pytest.fixture
def order_organizer_profile(test_user_order_org):
    """Fixture for the organizer profile in OrderForm tests."""
    return OrganizerProfile.objects.create(user=test_user_order_org)


@pytest.fixture
def event_for_ordering(order_organizer_profile):
    """Fixture for the main event used in OrderForm tests."""
    return Event.objects.create(
        organizer=order_organizer_profile,
        title="Event for Ordering",
        date=timezone.now().date(),
        time=timezone.now().time(),
    )


@pytest.fixture
def other_event_for_ordering(order_organizer_profile):
    """Fixture for a different event to test filtering."""
    return Event.objects.create(
        organizer=order_organizer_profile,
        title="Another Event",
        date=timezone.now().date(),
        time=timezone.now().time(),
    )


@pytest.fixture
def ticket_info_vip(event_for_ordering):
    """Fixture for the VIP TicketInfo."""
    return TicketInfo.objects.create(
        event=event_for_ordering, category="VIP", price=100, availability=10
    )


@pytest.fixture
def ticket_info_ga(event_for_ordering):
    """Fixture for the General Admission TicketInfo."""
    return TicketInfo.objects.create(
        event=event_for_ordering, category="General Admission", price=50, availability=5
    )


@pytest.fixture
def ticket_info_early_soldout(event_for_ordering):
    """Fixture for the sold-out Early Bird TicketInfo."""
    return TicketInfo.objects.create(
        event=event_for_ordering, category="Early Bird", price=40, availability=0
    )


@pytest.fixture
def ticket_info_other_event(other_event_for_ordering):
    """Fixture for a TicketInfo belonging to the 'other' event."""
    return TicketInfo.objects.create(
        event=other_event_for_ordering,
        category="General Admission",
        price=30,
        availability=100,
    )


def test_order_form_queryset_filtering(
    event_for_ordering,
    ticket_info_vip,
    ticket_info_ga,
    ticket_info_early_soldout,
    ticket_info_other_event,
):
    """Test that only available tickets for the correct event are shown."""
    form = OrderForm(event=event_for_ordering)  # Pass the event fixture
    queryset = form.fields["ticket_info"].queryset

    # Use standard assert statements
    assert ticket_info_other_event not in queryset
    assert ticket_info_vip in queryset
    assert ticket_info_ga in queryset
    assert ticket_info_early_soldout not in queryset
    assert queryset.count() == 2


def test_order_form_label_from_instance(event_for_ordering, ticket_info_vip):
    """Test the custom label format in the dropdown."""
    form = OrderForm(event=event_for_ordering)
    choices = list(form.fields["ticket_info"].choices)

    vip_choice_label = ""
    for value, label in choices:
        # Use value == ticket_info_vip.pk for comparison
        if value == ticket_info_vip.pk:
            vip_choice_label = label
            break

    expected_label = "VIP ($100.00) - 10 available"
    assert vip_choice_label == expected_label


def test_order_form_valid_data(event_for_ordering, ticket_info_ga):
    """Test submitting valid order data."""
    data = {
        "ticket_info": ticket_info_ga.pk,  # Use the pk from the fixture
        "full_name": "Test User",
        "email": "test@example.com",
        "phone": "555-1212-3333",
    }
    form = OrderForm(data, event=event_for_ordering)  # Pass data and event fixture

    # Use standard assert statements
    assert form.is_valid(), f"Form errors: {form.errors}"

    order = form.save(commit=False)
    assert order.ticket_info == ticket_info_ga
    assert order.full_name == "Test User"
    assert order.email == "test@example.com"
    assert order.phone == "555-1212-3333"


def test_order_form_invalid_data_missing_fields(event_for_ordering):
    """Test submitting with missing required fields."""
    data = {
        # Missing ticket_info
        # full_name is blank=True, so it's not required by the form
        "email": "test@example.com",
        "phone": "555-1212-3333",
    }
    form = OrderForm(data, event=event_for_ordering)

    # Use standard assert statements
    assert form.is_valid() is False
    assert "ticket_info" in form.errors


def test_order_form_invalid_ticket_choice(
    event_for_ordering, ticket_info_early_soldout
):
    """Test submitting with a ticket ID that shouldn't be available."""
    data = {
        "ticket_info": ticket_info_early_soldout.pk,  # Use sold-out ticket pk
        "full_name": "Test User",
        "email": "test@example.com",
        "phone": "555-1212-3333",
    }
    form = OrderForm(data, event=event_for_ordering)

    # Use standard assert statements
    assert form.is_valid() is False
    assert (
        "ticket_info" in form.errors
    )  # Fails validation against the filtered queryset
