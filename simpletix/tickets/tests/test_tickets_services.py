import pytest
from decimal import Decimal

from django.contrib.auth.models import User
from django.utils import timezone

from accounts.models import OrganizerProfile, UserProfile
from events.models import Event
from tickets.models import TicketInfo, Ticket
from tickets import services
from django.core import mail


pytestmark = pytest.mark.django_db


@pytest.fixture
def organizer_profile():
    user = User.objects.create_user(
        username="organizer_services",
        password="Passw0rd1!",
        email="org-services@example.com",
    )
    profile, _ = OrganizerProfile.objects.get_or_create(user=user)
    return profile


@pytest.fixture
def attendee_profile():
    user = User.objects.create_user(
        username="attendee_services",
        password="Passw0rd1!",
        email="attendee-services@example.com",
    )
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


@pytest.fixture
def event(organizer_profile):
    """
    Event fixture that matches how other tests create events:
    title, description, date, time, location are all non-null.
    """
    return Event.objects.create(
        organizer=organizer_profile,
        title="Services Test Event",
        description="Event for testing tickets.services functions",
        date=timezone.now().date(),
        time=timezone.now().time(),
        location="Services Test Location",
    )


@pytest.fixture
def ticket_info(event):
    """
    Use a valid category that exists in TicketInfo.CATEGORY_CHOICES.
    """
    return TicketInfo.objects.create(
        event=event,
        category="General Admission",
        price=Decimal("15.00"),
        availability=10,
    )


def test_issue_ticket_for_order_creates_ticket(attendee_profile, ticket_info):
    """
    Basic happy-path test for services.issue_ticket_for_order:
    - creates a Ticket
    - fills in the expected fields
    """
    assert Ticket.objects.count() == 0

    ticket = services.issue_ticket_for_order(
        order_id="order-svc-1",
        ticket_info=ticket_info,
        full_name="Service Tester",
        email="svc@example.com",
        phone="1234567890",
        attendee=attendee_profile,
    )

    assert Ticket.objects.count() == 1
    assert isinstance(ticket, Ticket)
    assert ticket.ticketInfo == ticket_info
    assert ticket.order_id == "order-svc-1"
    assert ticket.full_name == "Service Tester"
    assert ticket.email == "svc@example.com"
    assert ticket.phone == "1234567890"
    assert ticket.attendee == attendee_profile

    if hasattr(ticket, "qr_code"):
        assert ticket.qr_code is None or isinstance(ticket.qr_code, str)


def test_build_tickets_pdf_returns_bytes_or_none(ticket_info):
    """
    Call build_tickets_pdf with a real Ticket and simply assert that:
    - it doesn't raise, and
    - it returns either bytes/bytearray or None (depending on whether
      reportlab or similar is installed).
    """
    ticket = Ticket.objects.create(
        ticketInfo=ticket_info,
        order_id="order-svc-2",
        full_name="PDF User",
        email="pdf@example.com",
        phone="1112223333",
    )

    result = services.build_tickets_pdf([ticket])

    assert result is None or isinstance(result, (bytes, bytearray))


def test_send_ticket_email_does_not_raise(ticket_info, settings):
    """
    Smoke test for send_ticket_email.

    We rely on Django's email backend configuration in tests
    (usually locmem). We only assert that it does not raise,
    and returns None (which is the typical pattern).
    """
    ticket = Ticket.objects.create(
        ticketInfo=ticket_info,
        order_id="order-svc-3",
        full_name="Email User",
        email="email@example.com",
        phone="9999999999",
    )

    pdf_bytes = b"DUMMY-PDF"

    result = services.send_ticket_email(
        "email@example.com",
        [ticket],
        pdf_bytes,
    )

    assert result is None


def test_issue_ticket_for_order_keeps_availability_non_negative(ticket_info):
    """
    Calling issue_ticket_for_order must not make availability negative.
    Current implementation does not adjust availability, so we assert
    that the value stays >= 0 and does not increase.
    """
    start_availability = ticket_info.availability
    assert start_availability >= 0

    ticket = services.issue_ticket_for_order(
        order_id="order-svc-4",
        ticket_info=ticket_info,
        full_name="Inventory User",
        email="inv@example.com",
        phone="0001112222",
        attendee=None,
    )

    ticket_info.refresh_from_db()
    assert ticket is not None
    assert ticket_info.availability >= 0
    assert ticket_info.availability <= start_availability


def test_build_tickets_pdf_with_empty_list(ticket_info):
    """
    Exercise the code path for build_tickets_pdf([]), which may
    short-circuit and return None / empty bytes without doing any
    heavy work.
    """
    result = services.build_tickets_pdf([])
    assert result is None or isinstance(result, (bytes, bytearray))


def test_send_ticket_email_without_pdf_bytes(ticket_info, settings):
    """
    Many implementations support sending email without a PDF attachment.
    This covers the branch where pdf_bytes is omitted/None.
    """
    ticket = Ticket.objects.create(
        ticketInfo=ticket_info,
        order_id="order-svc-5",
        full_name="No PDF User",
        email="nopdf@example.com",
        phone="1231231234",
    )

    result = services.send_ticket_email(
        "nopdf@example.com",
        [ticket],
        None,
    )

    assert result is None


def test_issue_ticket_for_order_with_blank_fields(ticket_info):
    """
    Covers the branches where name/email/phone are empty or None and attendee is None.
    """
    ticket = services.issue_ticket_for_order(
        order_id="order-blank-fields",
        ticket_info=ticket_info,
        full_name="",
        email="",
        phone="",
        attendee=None,
    )

    ticket.refresh_from_db()

    assert ticket.full_name == ""
    assert ticket.email == ""
    assert ticket.phone == ""
    assert ticket.attendee is None
    assert ticket.status == "ISSUED"
    assert ticket.issued_at is not None
    assert ticket.qr_code.startswith("TCKT-")


def test_issue_ticket_for_order_with_blank_inputs(ticket_info):
    """
    Covers the branches where name/email/phone are empty or None and attendee is None.
    """
    ticket = services.issue_ticket_for_order(
        order_id="order-blank-fields",
        ticket_info=ticket_info,
        full_name="",
        email="",
        phone="",
        attendee=None,
    )

    ticket.refresh_from_db()

    assert ticket.full_name == ""
    assert ticket.email == ""
    assert ticket.phone == ""
    assert ticket.attendee is None
    assert ticket.status == "ISSUED"
    assert ticket.issued_at is not None
    assert ticket.qr_code.startswith("TCKT-")


def test_build_tickets_pdf_multiple_tickets(ticket_info):
    """
    Covers the multiple-ticket pagination branch (PageBreak).
    """
    ticket1 = Ticket.objects.create(
        ticketInfo=ticket_info,
        full_name="User One",
        email="one@example.com",
        phone="1111111111",
    )
    ticket2 = Ticket.objects.create(
        ticketInfo=ticket_info,
        full_name="User Two",
        email="two@example.com",
        phone="2222222222",
    )

    result = services.build_tickets_pdf([ticket1, ticket2])

    assert result is None or isinstance(result, (bytes, bytearray))


def test_send_ticket_email_with_empty_recipient(ticket_info):
    """
    Covers early return: if not to_email: return
    """
    ticket = Ticket.objects.create(
        ticketInfo=ticket_info,
        full_name="Nobody",
        email="",
        phone="000000",
    )

    result = services.send_ticket_email(
        "",
        [ticket],
        b"PDF",
    )

    assert result is None


def test_send_ticket_email_subject_contains_event_name(ticket_info):
    ticket = Ticket.objects.create(
        ticketInfo=ticket_info,
        full_name="Event User",
        email="eventuser@example.com",
        phone="8888888888",
    )

    services.send_ticket_email(
        "eventuser@example.com",
        [ticket],
        None,
    )

    assert len(mail.outbox) == 1
    email = mail.outbox[0]

    assert ticket_info.event.title in email.subject
