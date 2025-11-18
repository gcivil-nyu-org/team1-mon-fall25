from django.test import TestCase
from django.urls import reverse
from events.models import Event
from tickets.models import TicketInfo
from datetime import date, time


# Helper to create events with lat/lng
def create_event(title, lat, lng, days=0):
    e = Event.objects.create(
        title=title,
        description="test",
        location="Test Location",
        formatted_address="Test Address",
        latitude=lat,
        longitude=lng,
        date=date.today(),
        time=time(12, 0),
    )
    TicketInfo.objects.create(
        event=e, category="General Admission", price=50, availability=10
    )
    return e


class EventDistanceTests(TestCase):
    def setUp(self):
        # NYC
        self.ev1 = create_event("NYC Event", 40.7128, -74.0060)

        # Los Angeles
        self.ev2 = create_event("LA Event", 34.0522, -118.2437)

        # Chicago
        self.ev3 = create_event("Chicago Event", 41.8781, -87.6298)

    def test_nearest_first(self):
        url = reverse("events:event_list")
        response = self.client.get(
            url,
            {
                "distance_sort": "near",
                "user_lat": 40.7128,
                "user_lng": -74.0060,  # User in NYC
            },
        )

        events = list(response.context["events"])

        # NYC should appear first
        self.assertEqual(events[0].title, "NYC Event")

    def test_farthest_first(self):
        url = reverse("events:event_list")
        response = self.client.get(
            url,
            {
                "distance_sort": "far",
                "user_lat": 40.7128,
                "user_lng": -74.0060,  # NYC user
            },
        )

        events = list(response.context["events"])

        # LA should appear first because it's farthest from NYC
        self.assertEqual(events[0].title, "LA Event")

    def test_radius_filter(self):
        url = reverse("events:event_list")

        # radius 100 miles -> only NYC is within 100 miles of NYC
        response = self.client.get(
            url,
            {
                "radius": "100",
                "user_lat": 40.7128,
                "user_lng": -74.0060,
            },
        )

        events = list(response.context["events"])

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].title, "NYC Event")

    def test_missing_coordinates_does_not_crash(self):
        url = reverse("events:event_list")
        response = self.client.get(
            url,
            {
                "distance_sort": "near",
                # user_lat/user_lng missing
            },
        )

        # Should return all events without error
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["events"]), 3)
