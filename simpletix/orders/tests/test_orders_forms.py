import pytest
from django.contrib.auth.models import User
from django.utils import timezone

from events.models import Event
from accounts.models import OrganizerProfile
from tickets.models import TicketInfo
from orders.forms import OrderForm
from accounts.forms import OrganizerProfileForm

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
        "quantity": 1,
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
        "quantity": 1,
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
        "quantity": 1,
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


def test_order_form_preselect_valid_ticket(event_for_ordering, ticket_info_vip):
    """Test that a valid preselected ticket is set as initial value."""
    form = OrderForm(
        event=event_for_ordering, preselect_ticket_category_id=ticket_info_vip.id
    )
    assert form.initial["ticket_info"] == ticket_info_vip.id
    assert form.fields["quantity"].widget.attrs["max"] == ticket_info_vip.availability
    assert form.fields["quantity"].max_value == ticket_info_vip.availability


def test_order_form_preselect_invalid_ticket(event_for_ordering, ticket_info_vip):
    """Test an invalid preselected ticket falls back to the first available ticket."""
    invalid_id = 9999
    form = OrderForm(event=event_for_ordering, preselect_ticket_category_id=invalid_id)

    assert form.initial.get("ticket_info") is None
    first_ticket = form.fields["ticket_info"].queryset.first()

    assert form.fields["quantity"].widget.attrs["max"] == first_ticket.availability
    assert form.fields["quantity"].max_value == first_ticket.availability


def test_order_form_preselect_sold_out(event_for_ordering, ticket_info_early_soldout):
    """Test that a preselected ticket with 0 availability sets quantity max to 0."""
    form = OrderForm(
        event=event_for_ordering,
        preselect_ticket_category_id=ticket_info_early_soldout.id,
    )

    first_available = form.fields["ticket_info"].queryset.first()
    max_availability = first_available.availability if first_available else 0

    assert form.fields["quantity"].widget.attrs["max"] == max_availability
    assert form.fields["quantity"].max_value == max_availability


# requried and prefilled email


@pytest.fixture
def order_organizer_profile_with_email():
    """Fixture for the organizer profile in OrderForm tests."""
    test_user_order_org = User.objects.create_user(
        username="username", password="Passw0rd1!"
    )
    op = OrganizerProfile.objects.create(user=test_user_order_org)
    form = OrganizerProfileForm(
        data={
            "full_name": "A",
            "contact_email": "user@example.com",
            "phone": "1234567890",
        },
        instance=op,
    )
    return form.save()


# --- Form Tests ---


def test_order_form_email_mandatory(event_for_ordering, ticket_info_ga):
    """Test that email is required even if model says blank=True."""
    data = {
        "ticket_info": ticket_info_ga.pk,
        "quantity": 1,
        "full_name": "No Email User",
        "phone": "555-1212-3333",
        # "email" is intentionally missing
    }
    form = OrderForm(data, event=event_for_ordering, profile=None)

    assert not form.is_valid()
    assert "email" in form.errors
    assert "This field is required." in form.errors["email"]


def test_order_form_prefills_email_from_user(
    event_for_ordering, order_organizer_profile_with_email
):
    """Test that the form prefills email from the logged-in user."""
    # Initialize form with the user object, but NO data (GET request scenario)
    form = OrderForm(
        event=event_for_ordering, profile=order_organizer_profile_with_email
    )

    # Check the initial value of the email field
    assert form.fields["email"].initial == "user@example.com"
