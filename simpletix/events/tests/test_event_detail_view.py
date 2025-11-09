from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from events.models import Event
from accounts.models import OrganizerProfile
from datetime import date, time


class EventDetailViewTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="password")
        self.organizer_user = User.objects.create_user(
            username="organizer", password="password"
        )
        self.organizer_profile = OrganizerProfile.objects.create(
            user=self.organizer_user
        )

        self.event = Event.objects.create(
            title="Detail Test Event",
            description="Testing detail view",
            location="Test Location",
            organizer=self.organizer_profile,
            date=date(2025, 11, 7),
            time=time(19, 0),
            waitlist_enabled=True,
            ticket_limit=2,
        )

        self.client = Client()

    def test_event_detail_view_success(self):
        self.client.login(username="testuser", password="password")
        url = reverse("events:event_detail", args=[self.event.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.event.title)

    def test_event_detail_view_redirect_for_nonexistent_event(self):
        url = reverse("events:event_detail", args=[9999])

        # Not logged in → redirect
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

        # Logged in → 404
        self.client.login(username="testuser", password="password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
