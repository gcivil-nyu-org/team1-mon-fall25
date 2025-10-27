from django.test import TestCase
from django.urls import reverse

class EventListViewTest(TestCase):
    def test_event_list_view_loads(self):
        response = self.client.get(reverse("events:event_list"))
        self.assertEqual(response.status_code, 200)
