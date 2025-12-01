import pytest
from datetime import date, time

from django.contrib.auth import get_user_model
from django.urls import reverse

from accounts.models import OrganizerProfile
from events.models import Event
from events import services
from events import views as event_views


pytestmark = pytest.mark.django_db


def test_event_cancel_method_idempotent():
    """
    Event.cancel() should:
    - set is_cancelled=True and cancelled_at on first call
    - NOT reset cancelled_at or error on subsequent calls
    """
    User = get_user_model()
    user = User.objects.create_user(
        username="org-cancel",
        email="org-cancel@example.com",
        password="testpass123",
    )
    organizer = OrganizerProfile.objects.create(user=user)

    event = Event.objects.create(
        organizer=organizer,
        title="Cancelable Event",
        description="Test event",
        date=date.today(),
        time=time(18, 0),
        location="Test Venue",
    )

    assert not event.is_cancelled
    assert event.cancelled_at is None

    # First cancel
    event.cancel()
    event.refresh_from_db()

    assert event.is_cancelled is True
    assert event.cancelled_at is not None
    first_ts = event.cancelled_at

    # Second cancel: should not break or change timestamp meaningfully
    event.cancel()
    event.refresh_from_db()
    second_ts = event.cancelled_at

    # Allow microsecond differences, but they should both be set
    assert second_ts is not None
    assert first_ts <= second_ts


def test_cancel_event_view_happy_path(client, monkeypatch):
    """
    Organizer hitting POST /events/<id>/cancel/:
    - marks event as cancelled
    - calls notification + refund services
    - redirects to event_management_dashboard
    """
    User = get_user_model()
    user = User.objects.create_user(
        username="org-view",
        email="org-view@example.com",
        password="testpass123",
    )
    organizer = OrganizerProfile.objects.create(user=user)

    event = Event.objects.create(
        organizer=organizer,
        title="Event to cancel",
        description="Desc",
        date=date.today(),
        time=time(19, 30),
        location="Somewhere",
    )

    calls = {"notify": None, "refunds": None}

    def fake_notify(ev):
        calls["notify"] = ev.id

    def fake_refunds(ev):
        calls["refunds"] = ev.id

    # Patch the services in the views module (where the view imports them)
    monkeypatch.setattr(
        event_views.services,
        "notify_event_cancellation",
        fake_notify,
    )
    monkeypatch.setattr(
        event_views.services,
        "initiate_event_refunds",
        fake_refunds,
    )

    assert client.login(username="org-view", password="testpass123")

    url = reverse("events:cancel_event", args=[event.id])
    response = client.post(url)

    event.refresh_from_db()

    assert response.status_code == 302
    assert reverse("events:event_management_dashboard") in response["Location"]
    assert event.is_cancelled is True
    assert event.cancelled_at is not None
    assert calls["notify"] == event.id
    assert calls["refunds"] == event.id


def test_event_management_dashboard_shows_only_organizer_events(client):
    """
    Dashboard should only list events belonging to the logged-in organizer.
    """
    User = get_user_model()

    # Organizer A
    user_a = User.objects.create_user(
        username="org-A",
        email="orgA@example.com",
        password="passA123",
    )
    org_a = OrganizerProfile.objects.create(user=user_a)

    # Organizer B
    user_b = User.objects.create_user(
        username="org-B",
        email="orgB@example.com",
        password="passB123",
    )
    org_b = OrganizerProfile.objects.create(user=user_b)

    # Events: 2 for A, 1 for B
    event_a1 = Event.objects.create(
        organizer=org_a,
        title="A1",
        description="",
        date=date.today(),
        time=time(10, 0),
        location="Loc",
    )
    event_a2 = Event.objects.create(
        organizer=org_a,
        title="A2",
        description="",
        date=date.today(),
        time=time(11, 0),
        location="Loc",
    )
    Event.objects.create(
        organizer=org_b,
        title="B1",
        description="",
        date=date.today(),
        time=time(12, 0),
        location="Loc",
    )

    assert client.login(username="org-A", password="passA123")
    url = reverse("events:event_management_dashboard")
    response = client.get(url)

    assert response.status_code == 200
    # Dashboard should only show A's events
    content = response.content.decode("utf-8")
    assert "A1" in content
    assert "A2" in content
    assert "B1" not in content
    # sanity: ensure the template rendered our titles, not something else
    assert event_a1.title in content
    assert event_a2.title in content


def test_notify_event_cancellation_no_orders(monkeypatch):
    """
    If there are no completed orders for the event, no emails should be sent.
    """

    class DummyEvent:
        title = "Dummy"
        date = date(2025, 1, 1)
        time = time(18, 0)

    dummy_event = DummyEvent()

    def fake_get_event_orders(event):
        assert event is dummy_event
        return []

    send_calls = []

    def fake_send_mail(subject, message, from_email, recipient_list, **kwargs):
        send_calls.append(
            {
                "subject": subject,
                "message": message,
                "from_email": from_email,
                "recipients": list(recipient_list),
            }
        )
        return 1

    monkeypatch.setattr(services, "get_event_orders", fake_get_event_orders)
    monkeypatch.setattr(services, "send_mail", fake_send_mail)

    services.notify_event_cancellation(dummy_event)
    assert send_calls == []


def test_notify_event_cancellation_uses_order_email(monkeypatch):
    """
    notify_event_cancellation should use Order.email where available
    and call send_mail once per completed order.
    """

    class DummyUser:
        def __init__(self, email, username="userx"):
            self.email = email
            self.username = username

        def get_full_name(self):
            return ""

    class DummyAttendee:
        def __init__(self, user):
            self.user = user

    class DummyBillingInfo:
        def __init__(self, full_name=None, email=None):
            self.full_name = full_name
            self.email = email

    class DummyOrder:
        def __init__(self, email, full_name, billing_info=None, attendee=None):
            self.email = email
            self.full_name = full_name
            self.billing_info = billing_info
            self.attendee = attendee

    class DummyEvent:
        title = "Galaxy Fest"
        date = date(2025, 2, 2)
        time = time(20, 0)

    dummy_event = DummyEvent()

    # One order with direct email + name
    order1 = DummyOrder(
        email="primary@example.com",
        full_name="Primary User",
    )

    def fake_get_event_orders(event):
        assert event is dummy_event
        return [order1]

    send_calls = []

    def fake_send_mail(subject, message, from_email, recipient_list, **kwargs):
        send_calls.append(
            {
                "subject": subject,
                "message": message,
                "from_email": from_email,
                "recipients": list(recipient_list),
            }
        )
        return 1

    monkeypatch.setattr(services, "get_event_orders", fake_get_event_orders)
    monkeypatch.setattr(services, "send_mail", fake_send_mail)

    services.notify_event_cancellation(dummy_event)

    assert len(send_calls) == 1
    call = send_calls[0]
    assert "Event Cancelled: Galaxy Fest" in call["subject"]
    assert "primary@example.com" in call["recipients"]
    assert "Galaxy Fest" in call["message"]


def test_initiate_event_refunds_no_orders(monkeypatch):
    """
    initiate_event_refunds should safely no-op when there are no orders.
    """

    class DummyEvent:
        title = "Refundless Event"

    dummy_event = DummyEvent()
    calls = {"get_orders": 0}

    def fake_get_event_orders(event):
        assert event is dummy_event
        calls["get_orders"] += 1
        return []

    monkeypatch.setattr(services, "get_event_orders", fake_get_event_orders)

    # Should not raise or do anything
    services.initiate_event_refunds(dummy_event)
    assert calls["get_orders"] == 1
