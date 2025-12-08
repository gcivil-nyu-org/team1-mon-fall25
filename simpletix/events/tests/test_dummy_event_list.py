from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from datetime import date, time, timedelta
from events.models import Event
from accounts.models import OrganizerProfile
from tickets.models import TicketInfo


class EventListViewTest(TestCase):
    def setUp(self):
        """Create test data."""
        self.user = User.objects.create_user(username="testuser", password="pass123")
        self.organizer = OrganizerProfile.objects.create(
            user=self.user,
            full_name="Test Organizer",
            contact_email="testorg@example.com",
            phone="1234567890",
        )
        self.url = reverse("events:event_list")

    def test_event_list_view_loads(self):
        response = self.client.get(reverse("events:event_list"))
        self.assertEqual(response.status_code, 200)

    def test_event_list_displays_events(self):
        """Test that events appear in the list."""
        Event.objects.create(
            title="Test Event",
            description="Test Description",
            date=date.today() + timedelta(days=1),
            time=time(14, 0),
            location="Test Location",
            organizer=self.organizer,
        )
        response = self.client.get(self.url)
        self.assertContains(response, "Test Event")

    def test_event_list_empty(self):
        """Test event list with no events."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["events"]), 0)

    def test_event_list_multiple_events(self):
        """Test event list displays multiple events."""
        for i in range(3):
            Event.objects.create(
                title=f"Event {i}",
                description=f"Description {i}",
                date=date.today() + timedelta(days=i),
                time=time(14, 0),
                location=f"Location {i}",
                organizer=self.organizer,
            )
        response = self.client.get(self.url)
        self.assertEqual(len(response.context["events"]), 3)

    def test_event_list_date_sorting_soon(self):
        """Test sorting events by date (soonest first)."""
        # Create events with different dates
        Event.objects.create(
            title="Event 3",
            date=date.today() + timedelta(days=3),
            time=time(14, 0),
            location="Location",
            organizer=self.organizer,
        )
        Event.objects.create(
            title="Event 1",
            date=date.today() + timedelta(days=1),
            time=time(14, 0),
            location="Location",
            organizer=self.organizer,
        )

        response = self.client.get(self.url, {"date_sort": "soon"})
        events = list(response.context["events"])
        self.assertEqual(events[0].title, "Event 1")

    def test_event_list_date_range_filter(self):
        """Test filtering events by date range."""
        start = date.today() + timedelta(days=5)
        end = date.today() + timedelta(days=10)

        # Event within range
        Event.objects.create(
            title="In Range",
            date=date.today() + timedelta(days=7),
            time=time(14, 0),
            location="Location",
            organizer=self.organizer,
        )

        # Event outside range
        Event.objects.create(
            title="Out of Range",
            date=date.today() + timedelta(days=15),
            time=time(14, 0),
            location="Location",
            organizer=self.organizer,
        )

        response = self.client.get(
            self.url,
            {
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
            },
        )

        events = list(response.context["events"])
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].title, "In Range")

    def test_event_list_price_sorting(self):
        """Test sorting events by price."""
        event1 = Event.objects.create(
            title="Expensive Event",
            date=date.today() + timedelta(days=1),
            time=time(14, 0),
            location="Location",
            organizer=self.organizer,
        )
        TicketInfo.objects.create(
            event=event1,
            category="General Admission",
            price=100.00,
            availability=50,
        )

        event2 = Event.objects.create(
            title="Cheap Event",
            date=date.today() + timedelta(days=2),
            time=time(14, 0),
            location="Location",
            organizer=self.organizer,
        )
        TicketInfo.objects.create(
            event=event2,
            category="General Admission",
            price=20.00,
            availability=50,
        )

        # Sort by price ascending
        response = self.client.get(self.url, {"price_sort": "asc"})
        events = list(response.context["events"])
        self.assertEqual(events[0].title, "Cheap Event")
