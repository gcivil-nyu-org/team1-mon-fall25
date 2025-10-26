import pytest
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal

from events.models import Event
from accounts.models import OrganizerProfile, UserProfile
from tickets.models import TicketInfo, Ticket

# Mark all tests in this file as needing database access
pytestmark = pytest.mark.django_db


# --- View:order ---

@pytest.fixture
def organizer_user():
    """Fixture for the organizer user."""
    return User.objects.create_user(username='org_viewer', password='Passw0rd1!')

@pytest.fixture
def attendee_user():
    """Fixture for the attendee user."""
    return User.objects.create_user(username='att_viewer', password='Passw0rd1!')

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
    """Fixture for the event used in tests."""
    return Event.objects.create(
        organizer=organizer_profile,
        title='View Test Event',
        date=timezone.now().date(),
        time=timezone.now().time()
    )

@pytest.fixture
def ticket_info_vip(test_event):
    """Fixture for VIP TicketInfo."""
    return TicketInfo.objects.create(
        event=test_event, category='VIP', price=100, availability=1
    )

@pytest.fixture
def ticket_info_ga(test_event):
    """Fixture for General Admission TicketInfo."""
    return TicketInfo.objects.create(
        event=test_event, category='General Admission', price=50, availability=5
    )

@pytest.fixture
def ticket_info_soldout(test_event):
    """Fixture for Sold Out TicketInfo."""
    return TicketInfo.objects.create(
        event=test_event, category='Early Bird', price=40, availability=0
    )

@pytest.fixture
def order_url(test_event):
    """Fixture for the order URL."""
    return reverse('tickets:order', args=[test_event.id])

@pytest.fixture
def login_url():
    """Fixture for the login URL."""
    # Construct the URL with the role parameter for attendee
    base_url = reverse('accounts:login')
    return f"{base_url}?role=attendee"

@pytest.fixture
def logged_in_attendee_client(client, login_url, attendee_user):
    """Fixture for a client logged in as an attendee via the custom view."""
    login_data = {
        'username': attendee_user.username,
        'password': 'Passw0rd1!'
    }
    # Log in using the actual login view POST
    client.post(login_url, login_data, follow=True)
    # Verify session is set correctly after login
    assert client.session.get('desired_role') == 'attendee'
    return client

def test_order_view_get_request(logged_in_attendee_client, order_url, ticket_info_vip, ticket_info_ga, ticket_info_soldout):
    """Test GET request to the order page."""
    client = logged_in_attendee_client # Use the logged-in client fixture
    response = client.get(order_url)

    assert response.status_code == 200
    # Check template name used
    assert len(response.templates) > 0
    assert response.templates[0].name == 'tickets/order.html'
    assert 'form' in response.context
    assert 'event' in response.context

    # Check that the form's queryset is correctly filtered
    form = response.context['form']
    assert isinstance(form.fields['ticketInfo'].queryset.first(), TicketInfo)
    assert form.fields['ticketInfo'].queryset.count() == 2 # VIP and GA, not soldout
    assert ticket_info_soldout not in form.fields['ticketInfo'].queryset

def test_order_view_post_success_attendee(logged_in_attendee_client, order_url, ticket_info_ga, attendee_profile):
    """Test successful POST request as an attendee."""
    client = logged_in_attendee_client
    initial_availability = ticket_info_ga.availability
    data = {
        'ticketInfo': ticket_info_ga.pk,
        'full_name': 'Test Attendee Submit',
        'email': 'attendee@example.com',
        'phone': '111-222-3333'
    }
    response = client.post(order_url, data)

    # Check ticket creation
    assert Ticket.objects.count() == 1
    ticket = Ticket.objects.first()
    assert ticket.ticketInfo == ticket_info_ga
    assert ticket.full_name == 'Test Attendee Submit'
    assert ticket.attendee == attendee_profile # Check attendee profile was linked

    # Check availability decrement
    ticket_info_ga.refresh_from_db()
    assert ticket_info_ga.availability == initial_availability - 1

    # Check redirect using pytest-django helper
    expected_redirect_url = reverse('tickets:ticket_details', args=[ticket.id])
    assert response.status_code == 302
    assert response['location'] == expected_redirect_url # Check redirect location

def test_order_view_post_success_non_attendee(logged_in_attendee_client, order_url, ticket_info_vip):
    """Test successful POST request without attendee role hint during login."""
    client = logged_in_attendee_client
    client.logout()

    initial_availability = ticket_info_vip.availability
    initial_ticket_count = Ticket.objects.count() # Get count before POST
    data = {
        'ticketInfo': ticket_info_vip.pk,
        'full_name': 'Guest User Submit',
        'email': 'guest@example.com',
        'phone': '444-555-6666'
    }
    response = client.post(order_url, data)

    assert Ticket.objects.count() == initial_ticket_count + 1 # Check one ticket was created
    ticket = Ticket.objects.latest('id') # Get the newly created ticket
    assert ticket.ticketInfo == ticket_info_vip
    assert ticket.full_name == 'Guest User Submit'
    assert ticket.attendee is None # Check attendee was NOT linked based on view logic

    ticket_info_vip.refresh_from_db()
    assert ticket_info_vip.availability == initial_availability - 1

    expected_redirect_url = reverse('tickets:ticket_details', args=[ticket.id])
    assert response.status_code == 302
    assert response['location'] == expected_redirect_url

def test_order_view_post_invalid_data(logged_in_attendee_client, order_url, ticket_info_ga):
    """Test POST request with invalid form data."""
    client = logged_in_attendee_client
    initial_availability = ticket_info_ga.availability
    initial_ticket_count = Ticket.objects.count()
    data = {
        # Missing ticketInfo
        'full_name': '', # Still valid due to blank=True
        'email': 'invalid-email-format',
        'phone': '777-888-9999'
    }
    response = client.post(order_url, data)

    # Check no ticket created and availability unchanged
    assert Ticket.objects.count() == initial_ticket_count
    ticket_info_ga.refresh_from_db()
    assert ticket_info_ga.availability == initial_availability

    # Check form re-rendered with errors
    assert response.status_code == 200
    assert len(response.templates) > 0
    assert response.templates[0].name == 'tickets/order.html'
    assert 'form' in response.context
    form = response.context['form']
    assert form.errors # Check that errors exist
    assert 'ticketInfo' in form.errors
    assert 'email' in form.errors

def test_order_view_post_sold_out_ticket(logged_in_attendee_client, order_url, ticket_info_soldout):
    """Test POST request trying to buy a sold-out ticket."""
    client = logged_in_attendee_client
    initial_ticket_count = Ticket.objects.count()
    data = {
        'ticketInfo': ticket_info_soldout.pk, # Try to select the sold-out ticket
        'full_name': 'Late Comer',
        'email': 'late@example.com',
        'phone': '000-000-0000'
    }
    response = client.post(order_url, data)

    assert Ticket.objects.count() == initial_ticket_count # No ticket created
    assert response.status_code == 200 # Re-renders form
    assert 'form' in response.context
    form = response.context['form']
    assert form.errors
    assert 'ticketInfo' in form.errors # Fails validation because choice isn't available


# --- Views:details ---

@pytest.fixture
def details_ticket_info(test_event):
    """Fixture for the TicketInfo used in DetailsView tests."""
    return TicketInfo.objects.create(
        event=test_event, category='VIP', price=100, availability=10
    )

@pytest.fixture
def details_ticket(attendee_profile, details_ticket_info):
    """Fixture for the specific Ticket object being viewed."""
    return Ticket.objects.create(
        attendee=attendee_profile,
        ticketInfo=details_ticket_info,
        full_name="Detail Viewer",
        email="detail@example.com"
    )

@pytest.fixture
def details_url(details_ticket):
    """Fixture for the details URL of the specific ticket."""
    return reverse('tickets:ticket_details', args=[details_ticket.id])

def test_details_view_success(logged_in_attendee_client, details_url, details_ticket, test_event):
    """Test accessing the details page with a valid ticket ID."""
    client = logged_in_attendee_client # Use the specific logged-in client
    response = client.get(details_url) # Use the URL fixture

    assert response.status_code == 200
    # Check template name used
    assert len(response.templates) > 0
    assert response.templates[0].name == 'tickets/ticket_details.html'
    # Check context data using fixtures
    assert response.context['ticket'] == details_ticket
    assert response.context['event'] == test_event

def test_details_view_not_found(logged_in_attendee_client):
    """Test accessing the details page with an invalid ticket ID."""
    client = logged_in_attendee_client
    
    invalid_url = reverse('tickets:ticket_details', args=[9999]) # Non-existent ID
    response = client.get(invalid_url)

    assert response.status_code == 404


# --- Views:ticket_list ---

@pytest.fixture
def org_list_user():
    """Fixture for the organizer user in ListView tests."""
    return User.objects.create_user(username='org_list', password='Passw0rd1!')

@pytest.fixture
def list_organizer_profile(org_list_user):
    """Fixture for the organizer profile in ListView tests."""
    profile, _ = OrganizerProfile.objects.get_or_create(user=org_list_user)
    return profile

@pytest.fixture
def user1_list():
    """Fixture for the first attendee user in ListView tests."""
    return User.objects.create_user(username='user1_list', password='Passw0rd1!')

@pytest.fixture
def user2_list():
    """Fixture for the second attendee user in ListView tests."""
    return User.objects.create_user(username='user2_list', password='Passw0rd1!')

@pytest.fixture
def profile1_list(user1_list):
    """Fixture for the first attendee profile in ListView tests."""
    profile, _ = UserProfile.objects.get_or_create(user=user1_list, defaults={'role': 'attendee'})
    return profile

@pytest.fixture
def profile2_list(user2_list):
    """Fixture for the second attendee profile in ListView tests."""
    profile, _ = UserProfile.objects.get_or_create(user=user2_list, defaults={'role': 'attendee'})
    return profile

@pytest.fixture
def list_test_event(list_organizer_profile):
    """Fixture for the event used in ListView tests."""
    return Event.objects.create(
        organizer=list_organizer_profile,
        title='List Test Event',
        date=timezone.now().date(),
        time=timezone.now().time()
    )

@pytest.fixture
def list_ticket_info1(list_test_event):
    """Fixture for the first TicketInfo in ListView tests."""
    return TicketInfo.objects.create(event=list_test_event, category='General Admission', price=10)

@pytest.fixture
def list_ticket_info2(list_test_event):
    """Fixture for the second TicketInfo in ListView tests."""
    return TicketInfo.objects.create(event=list_test_event, category='VIP', price=50)

@pytest.fixture
def ticket1_user1(profile1_list, list_ticket_info1):
    """Fixture for user1's first ticket."""
    return Ticket.objects.create(attendee=profile1_list, ticketInfo=list_ticket_info1, full_name='User One GA')

@pytest.fixture
def ticket2_user1(profile1_list, list_ticket_info2):
    """Fixture for user1's second ticket."""
    return Ticket.objects.create(attendee=profile1_list, ticketInfo=list_ticket_info2, full_name='User One VIP')

@pytest.fixture
def ticket1_user2(profile2_list, list_ticket_info1):
    """Fixture for user2's ticket."""
    return Ticket.objects.create(attendee=profile2_list, ticketInfo=list_ticket_info1, full_name='User Two GA')

@pytest.fixture
def ticket_guest(list_ticket_info1):
    """Fixture for a ticket with no attendee."""
    return Ticket.objects.create(attendee=None, ticketInfo=list_ticket_info1, full_name='Guest')

@pytest.fixture
def list_url():
    """Fixture for the ticket list URL."""
    return reverse('tickets:ticket_list')

@pytest.fixture
def login_url_att():
    """Fixture for the base login URL."""
    return f"{reverse('accounts:login')}?role=attendee"

@pytest.fixture
def login_url_org():
    """Fixture for the base login URL."""
    return f"{reverse('accounts:login')}?role=organizer"

def test_ticket_list_attendee_role(
    client, login_url_att, user1_list, list_url,
    ticket1_user1, ticket2_user1 # Include ticket fixtures to ensure creation
):
    """Test list view when user has 'attendee' role in session."""
    # Log in user1 AS attendee using the custom login view
    login_data = {
        'username': user1_list.username,
        'password': 'Passw0rd1!'
    }
    client.post(login_url_att, login_data, follow=True)
    # Verify session is set
    assert client.session.get('desired_role') == 'attendee'

    # Now make the request
    response = client.get(list_url)
    assert response.status_code == 200
    # Check template name used
    assert len(response.templates) > 0
    assert response.templates[0].name == 'tickets/ticket_list.html'
    assert response.context['filtername'] == user1_list.username # Should be username

    # Check that only user1's tickets are present
    tickets_in_context = response.context['tickets']
    assert list(tickets_in_context.order_by('id')) == [ticket1_user1, ticket2_user1]


def test_ticket_list_guest_role(
    client, list_url,
    ticket1_user1, ticket2_user1, ticket1_user2, ticket_guest # Include all ticket fixtures
):
    """Test list view when user does not have 'attendee' role."""
    response = client.get(list_url)
    assert response.status_code == 200
    assert len(response.templates) > 0
    assert response.templates[0].name == 'tickets/ticket_list.html'
    assert response.context['filtername'] == 'all'

    # Check that ALL tickets are present
    tickets_in_context = response.context['tickets']
    expected_tickets = sorted(
        [ticket1_user1, ticket2_user1, ticket1_user2, ticket_guest],
        key=lambda t: t.id
    )
    assert list(tickets_in_context.order_by('id')) == expected_tickets

def test_ticket_list_org_role(
    client, login_url_org, org_list_user, list_url,
    ticket1_user1, ticket2_user1, ticket1_user2, ticket_guest # Include all ticket fixtures
):
    """Test list view when user does not have 'attendee' role."""
    # Log in user1 AS attendee using the custom login view
    login_data = {
        'username': org_list_user.username,
        'password': 'Passw0rd1!'
    }
    client.post(login_url_org, login_data, follow=True)
    # Verify session is set
    assert client.session.get('desired_role') == 'organizer'

    response = client.get(list_url)
    assert response.status_code == 200
    assert len(response.templates) > 0
    assert response.templates[0].name == 'tickets/ticket_list.html'
    assert response.context['filtername'] == 'all'

    # Check that ALL tickets are present
    tickets_in_context = response.context['tickets']
    expected_tickets = sorted(
        [ticket1_user1, ticket2_user1, ticket1_user2, ticket_guest],
        key=lambda t: t.id
    )
    assert list(tickets_in_context.order_by('id')) == expected_tickets

