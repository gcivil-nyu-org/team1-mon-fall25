# events/tests/test_events_views.py

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from datetime import date, time

from events.models import Event, Waitlist
from accounts.models import OrganizerProfile
from tickets.models import TicketInfo


class SimpleEventViewTests(TestCase):
    def setUp(self):
        # Create users
        self.user = User.objects.create_user(username="testuser", password="password")
        self.organizer_user = User.objects.create_user(
            username="organizer", password="password"
        )
        self.organizer_profile = OrganizerProfile.objects.create(
            user=self.organizer_user
        )

        # Create a test event
        self.event = Event.objects.create(
            title="Test Event",
            description="Test description",
            location="Test Location",
            organizer=self.organizer_profile,
            date=date(2025, 11, 7),
            time=time(19, 0),
            waitlist_enabled=True,
            ticket_limit=2,
        )

        # Add a ticket
        self.ticket = TicketInfo.objects.create(
            event=self.event, category="GEN", price=50, availability=2
        )

        # Client for requests
        self.client = Client()

    def login_as_organizer(self):
        """Helper to login as organizer and set session key for role"""
        self.client.login(username="organizer", password="password")
        session = self.client.session
        session["desired_role"] = "organizer"
        session.save()

    # -----------------------------
    # Event list/detail tests
    # -----------------------------
    def test_event_list_view(self):
        url = reverse("events:event_list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.event.title)

    def test_event_detail_view(self):
        self.client.login(username="testuser", password="password")
        url = reverse("events:event_detail", args=[self.event.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.event.title)

    def test_event_detail_view_redirect_for_nonexistent_event(self):
        url = reverse("events:event_detail", args=[999])
        # Not logged in -> redirect
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        # Logged in -> 404
        self.client.login(username="testuser", password="password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    # -----------------------------
    # Organizer-only views
    # -----------------------------
    def test_event_create_view_get(self):
        self.login_as_organizer()
        url = reverse("events:create_event")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Create Event")

    def test_event_edit_view_get(self):
        self.login_as_organizer()
        url = reverse("events:edit_event", args=[self.event.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Edit Event")

    def test_event_delete_view_get(self):
        self.login_as_organizer()
        url = reverse("events:delete_event", args=[self.event.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Delete Event")

    # -----------------------------
    # Waitlist tests
    # -----------------------------
    def test_join_waitlist(self):
        self.client.login(username="testuser", password="password")
        url = reverse("events:event_detail", args=[self.event.id])
        # Simulate tickets sold out
        self.ticket.availability = 0
        self.ticket.save()
        response = self.client.post(url)
        self.assertRedirects(response, url)
        self.assertTrue(
            Waitlist.objects.filter(user=self.user, event=self.event).exists()
        )

    def test_manage_waitlist_approval(self):
        entry = Waitlist.objects.create(user=self.user, event=self.event)
        self.login_as_organizer()
        url = reverse("events:manage_waitlist", args=[self.event.id])
        response = self.client.post(url, {"entry_id": entry.id, "action": "approve"})
        self.assertRedirects(response, url)
        entry.refresh_from_db()
        self.assertTrue(entry.is_approved)
