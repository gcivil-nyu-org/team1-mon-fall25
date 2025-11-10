import json
from datetime import date, time as time_

import pytest
from django.urls import reverse
from django.contrib.messages import get_messages

from events.models import Event
from tickets.models import Ticket, TicketInfo


# ---------- Helpers ----------


def _make_event():
    return Event.objects.create(
        title="Test Event",
        description="Test Description",
        date=date(2025, 10, 28),
        time=time_(12, 0, 0),
        location="Test Location",
    )


def _make_ticket_info(event, price=25, availability=10):
    return TicketInfo.objects.create(
        event=event,
        category="general",  # any string is fine; choices aren't enforced at DB level
        price=price,
        availability=availability,
    )


# ---------- payment_confirm tests ----------


@pytest.mark.django_db
def test_payment_confirm_non_post_returns_405(client):
    url = reverse("tickets:payment_confirm")
    response = client.get(url)
    assert response.status_code == 405  # HttpResponseNotAllowed


@pytest.mark.django_db
def test_payment_confirm_invalid_json_returns_400(client):
    url = reverse("tickets:payment_confirm")
    response = client.post(
        url,
        data="not-json",
        content_type="application/json",
    )
    assert response.status_code == 400
    assert response.json()["error"] == "Invalid JSON"


@pytest.mark.django_db
def test_payment_confirm_missing_required_fields_returns_400(client):
    url = reverse("tickets:payment_confirm")
    # Missing ticket_info_id and email
    payload = {"order_id": "order-123"}
    response = client.post(
        url,
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert response.status_code == 400
    assert (
        "order_id, ticket_info_id, and email are required" in response.json()["error"]
    )


@pytest.mark.django_db
def test_payment_confirm_success_happy_path(client, monkeypatch):
    """
    Exercise the main success flow of payment_confirm without actually
    calling the real services or sending email.
    """
    event = _make_event()
    ticket_info = _make_ticket_info(event)

    # Stub ticket object returned by services.issue_ticket_for_order
    class DummyTicket:
        def __init__(self, id, order_id):
            self.id = id
            self.order_id = order_id

    dummy_ticket = DummyTicket(id=42, order_id="order-xyz")

    issued_kwargs = {}
    sent_kwargs = {}

    def fake_issue_ticket_for_order(**kwargs):
        issued_kwargs.update(kwargs)
        return dummy_ticket

    def fake_build_tickets_pdf(tickets):
        # Just prove it's called
        assert tickets == [dummy_ticket]
        return b"PDF-BYTES"

    def fake_send_ticket_email(email, tickets, pdf_bytes):
        sent_kwargs["email"] = email
        sent_kwargs["tickets"] = tickets
        sent_kwargs["pdf_bytes"] = pdf_bytes

    # Patch the services used inside the view
    monkeypatch.setattr(
        "tickets.views.services.issue_ticket_for_order",
        fake_issue_ticket_for_order,
    )
    monkeypatch.setattr(
        "tickets.views.services.build_tickets_pdf",
        fake_build_tickets_pdf,
    )
    monkeypatch.setattr(
        "tickets.views.services.send_ticket_email",
        fake_send_ticket_email,
    )

    url = reverse("tickets:payment_confirm")
    payload = {
        "order_id": "order-xyz",
        "ticket_info_id": ticket_info.id,
        "full_name": "John Doe",
        "email": "john@example.com",
        "phone": "1234567890",
    }
    response = client.post(
        url,
        data=json.dumps(payload),
        content_type="application/json",
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["ticket_id"] == dummy_ticket.id
    assert data["order_id"] == dummy_ticket.order_id

    # Make sure our stubs were actually exercised
    assert issued_kwargs["order_id"] == "order-xyz"
    assert issued_kwargs["ticket_info"] == ticket_info
    assert sent_kwargs["email"] == "john@example.com"
    assert sent_kwargs["tickets"] == [dummy_ticket]
    assert sent_kwargs["pdf_bytes"] == b"PDF-BYTES"


# ---------- ticket_thank_you tests ----------


@pytest.mark.django_db
def test_ticket_thank_you_success_renders_qr_and_context(client):
    """
    Covers:
    - finding tickets by order_id
    - _qr_data_url_for_ticket, including the branch that generates qr_code
    - context values in the template
    """
    event = _make_event()
    ticket_info = _make_ticket_info(event)

    ticket = Ticket.objects.create(
        ticketInfo=ticket_info,
        order_id="order-777",
        full_name="Alice",
        email="alice@example.com",
        phone="9999999999",
    )

    url = reverse("tickets:ticket_thank_you", kwargs={"order_id": "order-777"})
    response = client.get(url)

    assert response.status_code == 200
    ctx = response.context
    assert ctx["order_id"] == "order-777"
    assert ctx["primary_ticket"] == ticket
    assert ctx["event"] == event
    assert isinstance(ctx["qr_data_url"], str)
    assert ctx["qr_data_url"].startswith("data:image/png;base64,")


@pytest.mark.django_db
def test_ticket_thank_you_no_tickets_returns_404(client):
    url = reverse("tickets:ticket_thank_you", kwargs={"order_id": "no-such-order"})
    response = client.get(url)
    assert response.status_code == 404


# ---------- ticket_resend tests ----------


@pytest.mark.django_db
def test_ticket_resend_success(monkeypatch, client):
    event = _make_event()
    ticket_info = _make_ticket_info(event)

    # Two tickets for same order_id to exercise list() in view
    ticket1 = Ticket.objects.create(
        ticketInfo=ticket_info,
        order_id="order-resend",
        full_name="Bob",
        email="bob@example.com",
        phone="123",
    )
    Ticket.objects.create(
        ticketInfo=ticket_info,
        order_id="order-resend",
        full_name="Bob 2",
        email="bob@example.com",
        phone="456",
    )

    pdf_called = {}
    email_called = {}

    def fake_build_tickets_pdf(tickets):
        pdf_called["tickets"] = tickets
        return b"PDF-RESEND"

    def fake_send_ticket_email(email, tickets, pdf_bytes=None):
        email_called["email"] = email
        email_called["tickets"] = tickets
        email_called["pdf_bytes"] = pdf_bytes

    monkeypatch.setattr("tickets.views.build_tickets_pdf", fake_build_tickets_pdf)
    monkeypatch.setattr("tickets.views.send_ticket_email", fake_send_ticket_email)

    url = reverse("tickets:ticket_resend", kwargs={"order_id": "order-resend"})
    response = client.post(url)

    # Should redirect back to thank_you page
    assert response.status_code == 302
    assert (
        reverse("tickets:ticket_thank_you", kwargs={"order_id": "order-resend"})
        in response["Location"]
    )

    # Make sure our fake email + pdf handlers were used
    assert email_called["email"] == ticket1.email
    assert len(email_called["tickets"]) == 2
    assert email_called["pdf_bytes"] == b"PDF-RESEND"

    # And messages framework was used
    msgs = list(get_messages(response.wsgi_request))
    assert any("re-sent your tickets" in str(m) for m in msgs)


@pytest.mark.django_db
def test_ticket_resend_no_tickets_sets_error_message_and_redirects(client):
    url = reverse("tickets:ticket_resend", kwargs={"order_id": "missing-order"})
    response = client.post(url)

    assert response.status_code == 302
    assert (
        reverse("tickets:ticket_thank_you", kwargs={"order_id": "missing-order"})
        in response["Location"]
    )

    msgs = list(get_messages(response.wsgi_request))
    assert any("couldn't find any tickets" in str(m) for m in msgs)


@pytest.mark.django_db
def test_ticket_resend_missing_email_sets_error_message(client):
    event = _make_event()
    ticket_info = _make_ticket_info(event)

    # Ticket with empty email triggers the "no email" branch
    Ticket.objects.create(
        ticketInfo=ticket_info,
        order_id="order-no-email",
        full_name="No Email User",
        email="",
        phone="123",
    )

    url = reverse("tickets:ticket_resend", kwargs={"order_id": "order-no-email"})
    response = client.post(url)

    assert response.status_code == 302
    assert (
        reverse("tickets:ticket_thank_you", kwargs={"order_id": "order-no-email"})
        in response["Location"]
    )

    msgs = list(get_messages(response.wsgi_request))
    assert any("doesn't have an email address saved" in str(m) for m in msgs)
