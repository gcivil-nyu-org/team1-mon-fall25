import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
from django import forms

from events.models import Event
from accounts.models import OrganizerProfile
from tickets.models import TicketInfo
from tickets.forms import TicketFormSet, OrderForm

pytestmark = pytest.mark.django_db


# --- forms:TicketInfoForm ---

@pytest.fixture
def test_user_org():
    """Fixture to create a test user."""
    return User.objects.create_user(username='testorg', password='Passw0rd1!')

@pytest.fixture
def organizer_profile(test_user_org):
    """Fixture to create an organizer profile linked to the test user."""
    return OrganizerProfile.objects.create(user=test_user_org)

@pytest.fixture
def test_event_for_formset(organizer_profile):
    """Fixture to create a test event for the formset tests."""
    return Event.objects.create(
        organizer=organizer_profile,
        title='Test Event for Formset',
        date=timezone.now().date(),
        time=timezone.now().time()
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
    assert formset.can_delete is False # Use 'is False' for boolean


def test_formset_widget_is_hidden_input(test_event_for_formset, formset_prefix):
    """Check if the category field uses HiddenInput."""
    formset = TicketFormSet(instance=test_event_for_formset, prefix=formset_prefix)
    first_form = formset.forms[0]
    # Use standard assert statements
    assert isinstance(first_form.fields['category'].widget, forms.HiddenInput)

def test_formset_valid_data(test_event_for_formset, formset_prefix):
    """Test submitting valid data for the formset."""
    event = test_event_for_formset # Get the event instance from the fixture
    data = {
        f'{formset_prefix}-TOTAL_FORMS': '3',
        f'{formset_prefix}-INITIAL_FORMS': '0',
        f'{formset_prefix}-MIN_NUM_FORMS': '3',
        f'{formset_prefix}-MAX_NUM_FORMS': '3',
        f'{formset_prefix}-0-category': 'General Admission',
        f'{formset_prefix}-0-price': '20.00',
        f'{formset_prefix}-0-availability': '100',
        f'{formset_prefix}-1-category': 'VIP',
        f'{formset_prefix}-1-price': '50.00',
        f'{formset_prefix}-1-availability': '20',
        f'{formset_prefix}-2-category': 'Early Bird',
        f'{formset_prefix}-2-price': '15.00',
        f'{formset_prefix}-2-availability': '50',
    }
    formset = TicketFormSet(data, instance=event, prefix=formset_prefix)
    
    # Use standard assert statements, provide better error message on failure
    assert formset.is_valid(), f"Formset errors: {formset.errors}" 
    
    instances = formset.save()
    assert len(instances) == 3
    assert TicketInfo.objects.filter(event=event).count() == 3
    vip_ticket = TicketInfo.objects.get(event=event, category='VIP')
    assert vip_ticket.price == Decimal('50.00')

def test_formset_invalid_data_missing_field(test_event_for_formset, formset_prefix):
    """Test submitting invalid data (missing price)."""
    event = test_event_for_formset
    data = {
        # --- Management Form Data ---
        f'{formset_prefix}-TOTAL_FORMS': '3',
        f'{formset_prefix}-INITIAL_FORMS': '0',
        f'{formset_prefix}-MIN_NUM_FORMS': '3',
        f'{formset_prefix}-MAX_NUM_FORMS': '3',
        # --- Form Data ---
        f'{formset_prefix}-0-category': 'General Admission',
        f'{formset_prefix}-0-price': '20.00',
        f'{formset_prefix}-0-availability': '100',
        f'{formset_prefix}-1-category': 'VIP',
        # Missing price for VIP (formset index 1)
        f'{formset_prefix}-1-availability': '20',
        f'{formset_prefix}-2-category': 'Early Bird',
        f'{formset_prefix}-2-price': '15.00',
        f'{formset_prefix}-2-availability': '50',
    }
    formset = TicketFormSet(data, instance=event, prefix=formset_prefix)
    
    # Use standard assert statements
    assert formset.is_valid() is False # Check it's invalid
    assert len(formset.errors) == 3    # Expect errors for 3 forms
    assert 'price' in formset.errors[1] # Check specific error in 2nd form
    assert 'This field is required.' in formset.errors[1]['price']


# --- forms:OrderForm ---

@pytest.fixture
def test_user_order_org():
    """Fixture for the organizer user in OrderForm tests."""
    return User.objects.create_user(username='testorderorg', password='Passw0rd1!')

@pytest.fixture
def order_organizer_profile(test_user_order_org):
    """Fixture for the organizer profile in OrderForm tests."""
    return OrganizerProfile.objects.create(user=test_user_order_org)

@pytest.fixture
def event_for_ordering(order_organizer_profile):
    """Fixture for the main event used in OrderForm tests."""
    return Event.objects.create(
        organizer=order_organizer_profile,
        title='Event for Ordering',
        date=timezone.now().date(),
        time=timezone.now().time()
    )

@pytest.fixture
def other_event_for_ordering(order_organizer_profile):
    """Fixture for a different event to test filtering."""
    return Event.objects.create(
        organizer=order_organizer_profile,
        title='Another Event',
        date=timezone.now().date(),
        time=timezone.now().time()
    )

@pytest.fixture
def ticket_info_vip(event_for_ordering):
    """Fixture for the VIP TicketInfo."""
    return TicketInfo.objects.create(
        event=event_for_ordering, category='VIP', price=100, availability=10
    )

@pytest.fixture
def ticket_info_ga(event_for_ordering):
    """Fixture for the General Admission TicketInfo."""
    return TicketInfo.objects.create(
        event=event_for_ordering, category='General Admission', price=50, availability=5
    )

@pytest.fixture
def ticket_info_early_soldout(event_for_ordering):
    """Fixture for the sold-out Early Bird TicketInfo."""
    return TicketInfo.objects.create(
        event=event_for_ordering, category='Early Bird', price=40, availability=0
    )

@pytest.fixture
def ticket_info_other_event(other_event_for_ordering):
    """Fixture for a TicketInfo belonging to the 'other' event."""
    return TicketInfo.objects.create(
         event=other_event_for_ordering, category='General Admission', price=30, availability=100
    )

def test_order_form_queryset_filtering(
    event_for_ordering, ticket_info_vip, ticket_info_ga,
    ticket_info_early_soldout, ticket_info_other_event
):
    """Test that only available tickets for the correct event are shown."""
    form = OrderForm(event=event_for_ordering) # Pass the event fixture
    queryset = form.fields['ticketInfo'].queryset

    # Use standard assert statements
    assert ticket_info_other_event not in queryset
    assert ticket_info_vip in queryset
    assert ticket_info_ga in queryset
    assert ticket_info_early_soldout not in queryset
    assert queryset.count() == 2

def test_order_form_label_from_instance(event_for_ordering, ticket_info_vip):
    """Test the custom label format in the dropdown."""
    form = OrderForm(event=event_for_ordering)
    choices = list(form.fields['ticketInfo'].choices)

    vip_choice_label = ""
    for value, label in choices:
        # Use value == ticket_info_vip.pk for comparison
        if value == ticket_info_vip.pk:
            vip_choice_label = label
            break
            
    expected_label = f"VIP ($100.00) - 10 available"
    assert vip_choice_label == expected_label

def test_order_form_valid_data(event_for_ordering, ticket_info_ga):
    """Test submitting valid order data."""
    data = {
        'ticketInfo': ticket_info_ga.pk, # Use the pk from the fixture
        'full_name': 'Test User',
        'email': 'test@example.com',
        'phone': '555-1212-3333'
    }
    form = OrderForm(data, event=event_for_ordering) # Pass data and event fixture
    
    # Use standard assert statements
    assert form.is_valid(), f"Form errors: {form.errors}"
    
    ticket = form.save(commit=False)
    assert ticket.ticketInfo == ticket_info_ga
    assert ticket.full_name == 'Test User'
    assert ticket.email == 'test@example.com'
    assert ticket.phone == '555-1212-3333'

def test_order_form_invalid_data_missing_fields(event_for_ordering):
    """Test submitting with missing required fields."""
    data = {
        # Missing ticketInfo
        # full_name is blank=True, so it's not required by the form
        'email': 'test@example.com',
        'phone': '555-1212-3333'
    }
    form = OrderForm(data, event=event_for_ordering)
    
    # Use standard assert statements
    assert form.is_valid() is False
    assert 'ticketInfo' in form.errors

def test_order_form_invalid_ticket_choice(event_for_ordering, ticket_info_early_soldout):
    """Test submitting with a ticket ID that shouldn't be available."""
    data = {
        'ticketInfo': ticket_info_early_soldout.pk, # Use sold-out ticket pk
        'full_name': 'Test User',
        'email': 'test@example.com',
        'phone': '555-1212-3333'
    }
    form = OrderForm(data, event=event_for_ordering)
    
    # Use standard assert statements
    assert form.is_valid() is False
    assert 'ticketInfo' in form.errors # Fails validation against the filtered queryset
