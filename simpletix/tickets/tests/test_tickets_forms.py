import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
from django import forms

from events.models import Event
from accounts.models import OrganizerProfile
from tickets.models import TicketInfo
from tickets.forms import TicketFormSet

pytestmark = pytest.mark.django_db


# --- forms:TicketInfoForm ---


@pytest.fixture
def test_user_org():
    """Fixture to create a test user."""
    return User.objects.create_user(username="testorg", password="Passw0rd1!")


@pytest.fixture
def organizer_profile(test_user_org):
    """Fixture to create an organizer profile linked to the test user."""
    return OrganizerProfile.objects.create(user=test_user_org)


@pytest.fixture
def test_event_for_formset(organizer_profile):
    """Fixture to create a test event for the formset tests."""
    return Event.objects.create(
        organizer=organizer_profile,
        title="Test Event for Formset",
        date=timezone.now().date(),
        time=timezone.now().time(),
    )


@pytest.fixture
def formset_prefix():
    """Fixture to provide the default formset prefix."""
    return TicketFormSet.get_default_prefix()


def test_formset_configuration(test_event_for_formset, formset_prefix):
    """Verify extra, min_num, max_num settings."""
    # Pass the event fixture directly
    formset = TicketFormSet(instance=test_event_for_formset, prefix=formset_prefix)

    # Use standard assert statements
    assert len(formset.forms) == 3
    assert formset.extra == 3
    assert formset.min_num == 3
    assert formset.max_num == 3
    assert formset.can_delete is False  # Use 'is False' for boolean


def test_formset_widget_is_hidden_input(test_event_for_formset, formset_prefix):
    """Check if the category field uses HiddenInput."""
    formset = TicketFormSet(instance=test_event_for_formset, prefix=formset_prefix)
    first_form = formset.forms[0]
    # Use standard assert statements
    assert isinstance(first_form.fields["category"].widget, forms.HiddenInput)


def test_formset_valid_data(test_event_for_formset, formset_prefix):
    """Test submitting valid data for the formset."""
    event = test_event_for_formset  # Get the event instance from the fixture
    data = {
        f"{formset_prefix}-TOTAL_FORMS": "3",
        f"{formset_prefix}-INITIAL_FORMS": "0",
        f"{formset_prefix}-MIN_NUM_FORMS": "3",
        f"{formset_prefix}-MAX_NUM_FORMS": "3",
        f"{formset_prefix}-0-category": "General Admission",
        f"{formset_prefix}-0-price": "20.00",
        f"{formset_prefix}-0-availability": "100",
        f"{formset_prefix}-1-category": "VIP",
        f"{formset_prefix}-1-price": "50.00",
        f"{formset_prefix}-1-availability": "20",
        f"{formset_prefix}-2-category": "Early Bird",
        f"{formset_prefix}-2-price": "15.00",
        f"{formset_prefix}-2-availability": "50",
    }
    formset = TicketFormSet(data, instance=event, prefix=formset_prefix)

    # Use standard assert statements, provide better error message on failure
    assert formset.is_valid(), f"Formset errors: {formset.errors}"

    instances = formset.save()
    assert len(instances) == 3
    assert TicketInfo.objects.filter(event=event).count() == 3
    vip_ticket = TicketInfo.objects.get(event=event, category="VIP")
    assert vip_ticket.price == Decimal("50.00")


def test_formset_invalid_data_missing_field(test_event_for_formset, formset_prefix):
    """Test submitting invalid data (missing price)."""
    event = test_event_for_formset
    data = {
        # --- Management Form Data ---
        f"{formset_prefix}-TOTAL_FORMS": "3",
        f"{formset_prefix}-INITIAL_FORMS": "0",
        f"{formset_prefix}-MIN_NUM_FORMS": "3",
        f"{formset_prefix}-MAX_NUM_FORMS": "3",
        # --- Form Data ---
        f"{formset_prefix}-0-category": "General Admission",
        f"{formset_prefix}-0-price": "20.00",
        f"{formset_prefix}-0-availability": "100",
        f"{formset_prefix}-1-category": "VIP",
        # Missing price for VIP (formset index 1)
        f"{formset_prefix}-1-availability": "20",
        f"{formset_prefix}-2-category": "Early Bird",
        f"{formset_prefix}-2-price": "15.00",
        f"{formset_prefix}-2-availability": "50",
    }
    formset = TicketFormSet(data, instance=event, prefix=formset_prefix)

    # Use standard assert statements
    assert formset.is_valid() is False  # Check it's invalid
    assert len(formset.errors) == 3  # Expect errors for 3 forms
    assert "price" in formset.errors[1]  # Check specific error in 2nd form
    assert "This field is required." in formset.errors[1]["price"]

