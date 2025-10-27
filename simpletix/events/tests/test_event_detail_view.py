from django.test import TestCase
from django.urls import reverse


class EventDetailViewTest(TestCase):
    def test_event_detail_view_returns_404_for_nonexistent_event(self):
        # Trying to access a non-existent event should return 404
        response = self.client.get(reverse("events:event_detail", args=[999]))
        self.assertEqual(response.status_code, 404)
