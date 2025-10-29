from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from events.models import Event
from accounts.models import OrganizerProfile  # make sure this is correct


class SimpleEventViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="pass123")
        self.organizer = OrganizerProfile.objects.create(
            user=self.user,
            full_name="Test Organizer",
            contact_email="testorg@example.com",
            phone="1234567890",
        )

        self.event = Event.objects.create(
            title="Test Event",
            description="Test Description",
            date="2025-10-28",
            time="12:00:00",
            location="Test Location",
            organizer=self.organizer,
        )

    def test_event_list_view(self):
        response = self.client.get(reverse("events:event_list"))
        self.assertEqual(response.status_code, 200)

    def test_event_detail_view(self):
        response = self.client.get(reverse("events:event_detail", args=[self.event.id]))
        self.assertEqual(response.status_code, 200)

    def test_event_create_view_get(self):
        self.client.login(username="testuser", password="testpass")
        url = reverse("events:create_event")
        response = self.client.get(url)
        # If your view redirects even for logged in users, adjust expected code
        self.assertIn(response.status_code, [200, 302])

    def test_event_edit_view_get(self):
        response = self.client.get(reverse("events:edit_event", args=[self.event.id]))
        self.assertIn(response.status_code, [200, 302])  # allows redirect or success

    def test_event_delete_view_get(self):
        response = self.client.get(reverse("events:delete_event", args=[self.event.id]))
        self.assertIn(response.status_code, [200, 302])
