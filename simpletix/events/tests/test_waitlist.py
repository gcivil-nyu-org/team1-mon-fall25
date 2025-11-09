from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from datetime import date, time

from events.models import Event, Waitlist
from accounts.models import OrganizerProfile
from tickets.models import TicketInfo


class WaitlistViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="password")
        self.organizer_user = User.objects.create_user(
            username="organizer", password="password"
        )
        self.organizer_profile = OrganizerProfile.objects.create(
            user=self.organizer_user
        )

        self.event = Event.objects.create(
            title="Waitlist Event",
            description="Waitlist test",
            location="Test Location",
            organizer=self.organizer_profile,
            date=date(2025, 11, 7),
            time=time(19, 0),
            waitlist_enabled=True,
            ticket_limit=1,
        )

        self.ticket = TicketInfo.objects.create(
            event=self.event,
            category="GEN",
            price=50,
            availability=0,  # Sold out to trigger waitlist
        )

        self.client = Client()

    def test_join_waitlist(self):
        self.client.login(username="testuser", password="password")
        url = reverse("events:join_waitlist", args=[self.event.id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Waitlist.objects.filter(user=self.user, event=self.event).exists()
        )

    def test_manage_waitlist_approval(self):
        entry = Waitlist.objects.create(user=self.user, event=self.event)
        self.client.login(username="organizer", password="password")
        url = reverse("events:manage_waitlist", args=[self.event.id])
        response = self.client.post(url, {"entry_id": entry.id, "action": "approve"})
        self.assertEqual(response.status_code, 302)
        entry.refresh_from_db()
        self.assertTrue(entry.is_approved)
