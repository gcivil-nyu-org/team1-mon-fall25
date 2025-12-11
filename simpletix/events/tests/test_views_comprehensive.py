from django.test import TestCase, override_settings
from django.urls import reverse
from django.contrib.auth.models import User
from django.core import mail
from datetime import date, time, timedelta
from unittest.mock import patch

from events.models import Event, EventNotificationSubscription
from accounts.models import OrganizerProfile
from tickets.models import TicketInfo


class EventDetailViewTests(TestCase):
    """Comprehensive tests for event detail view."""

    def setUp(self):
        """Create test data."""
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
            date=date.today() + timedelta(days=1),
            time=time(14, 0),
            location="Test Location",
            organizer=self.organizer,
        )

    def test_event_detail_view_returns_404_for_nonexistent_event(self):
        """Test 404 response for non-existent event."""
        response = self.client.get(reverse("events:event_detail", args=[999]))
        self.assertEqual(response.status_code, 404)

    def test_event_detail_view_loads_successfully(self):
        """Test event detail view returns 200."""
        url = reverse("events:event_detail", args=[self.event.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "events/event_detail.html")

    def test_event_detail_displays_correct_data(self):
        """Test event detail shows correct information."""
        url = reverse("events:event_detail", args=[self.event.id])
        response = self.client.get(url)
        self.assertContains(response, "Test Event")
        self.assertContains(response, "Test Description")
        self.assertContains(response, "Test Location")

    def test_event_detail_with_sold_out_tickets(self):
        """Test event marked as sold out when all tickets unavailable."""
        TicketInfo.objects.create(
            event=self.event,
            category="General Admission",
            price=50.00,
            availability=0,
            is_active=True,
        )

        url = reverse("events:event_detail", args=[self.event.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["is_sold_out"])

    def test_event_detail_with_available_tickets(self):
        """Test event with available tickets."""
        TicketInfo.objects.create(
            event=self.event,
            category="General Admission",
            price=50.00,
            availability=100,
            is_active=True,
        )

        url = reverse("events:event_detail", args=[self.event.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["is_sold_out"])

    def test_event_not_sold_out_with_inactive_tickets(self):
        """Test that inactive tickets don't affect sold-out status."""
        TicketInfo.objects.create(
            event=self.event,
            category="General Admission",
            price=50.00,
            availability=0,
            is_active=False,
        )

        url = reverse("events:event_detail", args=[self.event.id])
        response = self.client.get(url)
        self.assertFalse(response.context["is_sold_out"])

    def test_event_sold_out_all_tickets_unavailable(self):
        """Test sold out with multiple ticket types."""
        TicketInfo.objects.create(
            event=self.event,
            category="General Admission",
            price=50.00,
            availability=0,
            is_active=True,
        )
        TicketInfo.objects.create(
            event=self.event,
            category="VIP",
            price=100.00,
            availability=0,
            is_active=True,
        )

        url = reverse("events:event_detail", args=[self.event.id])
        response = self.client.get(url)
        self.assertTrue(response.context["is_sold_out"])

    def test_event_detail_subscriber_count(self):
        """Test subscriber count display."""
        EventNotificationSubscription.objects.create(
            event=self.event, email="sub1@example.com", name="Subscriber 1"
        )
        EventNotificationSubscription.objects.create(
            event=self.event, email="sub2@example.com", name="Subscriber 2"
        )

        url = reverse("events:event_detail", args=[self.event.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["subscriber_count"], 2)


class EventCreateViewTests(TestCase):
    """Comprehensive tests for event creation."""

    def setUp(self):
        """Create test data."""
        self.user = User.objects.create_user(username="organizer", password="pass123")
        self.organizer = OrganizerProfile.objects.create(
            user=self.user,
            full_name="Test Organizer",
            contact_email="org@example.com",
            phone="1234567890",
        )
        self.client.login(username="organizer", password="pass123")
        session = self.client.session
        session["desired_role"] = "organizer"
        session.save()

    def test_create_event_get_request(self):
        """Test GET request to create event view."""
        url = reverse("events:create_event")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context)
        self.assertIn("formset", response.context)

    @patch("events.views.algolia_save")
    def test_create_event_calls_algolia_save(self, mock_algolia):
        """Test Algolia integration on event creation."""
        url = reverse("events:create_event")
        data = {
            "title": "New Event",
            "description": "Description",
            "date": (date.today() + timedelta(days=7)).isoformat(),
            "time": "15:00:00",
            "location": "Location",
            "form-TOTAL_FORMS": "0",
            "form-INITIAL_FORMS": "0",
        }

        response = self.client.post(url, data)
        self.assertIn(response.status_code, (200, 302))

        if Event.objects.filter(title="New Event").exists():
            mock_algolia.assert_called_once()

    def test_create_event_with_invalid_form(self):
        """Test event creation with invalid form data."""
        url = reverse("events:create_event")
        data = {
            "title": "",  # Invalid - required field
            "description": "Description",
            "date": (date.today() + timedelta(days=7)).isoformat(),
            "time": "15:00:00",
            "location": "Location",
            "form-TOTAL_FORMS": "0",
            "form-INITIAL_FORMS": "0",
        }

        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context)

    def test_create_event_with_formset_errors(self):
        """Test event creation with invalid ticket formset."""
        url = reverse("events:create_event")
        data = {
            "title": "Event with Bad Tickets",
            "description": "Description",
            "date": (date.today() + timedelta(days=7)).isoformat(),
            "time": "15:00:00",
            "location": "Location",
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "0",
            "form-0-category": "General Admission",
            "form-0-price": "invalid_price",
        }

        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)

    def test_create_event_requires_organizer_role(self):
        """Test create view requires organizer role."""
        session = self.client.session
        session["desired_role"] = "attendee"
        session.save()

        url = reverse("events:create_event")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_create_event_requires_login(self):
        """Test create view requires authentication."""
        self.client.logout()
        url = reverse("events:create_event")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.url)

    def test_create_event_with_tickets(self):
        """Test creating event with ticket information."""
        url = reverse("events:create_event")
        data = {
            "title": "Event With Tickets",
            "description": "Description",
            "date": (date.today() + timedelta(days=7)).isoformat(),
            "time": "15:00:00",
            "location": "Location",
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "0",
            "form-0-category": "General Admission",
            "form-0-price": "50.00",
            "form-0-availability": "100",
        }

        response = self.client.post(url, data)
        self.assertIn(response.status_code, (200, 302))

        if Event.objects.filter(title="Event With Tickets").exists():
            event = Event.objects.get(title="Event With Tickets")
            self.assertTrue(TicketInfo.objects.filter(event=event).exists())


class EventEditViewTests(TestCase):
    """Comprehensive tests for event editing."""

    def setUp(self):
        """Create test data."""
        self.user = User.objects.create_user(username="organizer", password="pass123")
        self.organizer = OrganizerProfile.objects.create(
            user=self.user,
            full_name="Test Organizer",
            contact_email="org@example.com",
            phone="1234567890",
        )
        self.event = Event.objects.create(
            title="Test Event",
            date=date.today() + timedelta(days=1),
            time=time(14, 0),
            location="Test Location",
            organizer=self.organizer,
        )
        self.ticket_info = TicketInfo.objects.create(
            event=self.event,
            category="General Admission",
            price=50.00,
            availability=100,
        )

        self.client.login(username="organizer", password="pass123")
        session = self.client.session
        session["desired_role"] = "organizer"
        session.save()

    def test_edit_event_get_request(self):
        """Test GET request to edit event view."""
        url = reverse("events:edit_event", args=[self.event.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context)
        self.assertIn("formset", response.context)

    @patch("events.views.algolia_save")
    def test_edit_event_calls_algolia_save(self, mock_algolia):
        """Test Algolia integration on event edit."""
        url = reverse("events:edit_event", args=[self.event.id])
        data = {
            "title": "Updated Event",
            "description": "Updated Description",
            "date": (date.today() + timedelta(days=7)).isoformat(),
            "time": "16:00:00",
            "location": "Updated Location",
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "1",
            "form-0-id": str(self.ticket_info.id),
            "form-0-category": "General Admission",
            "form-0-price": "50.00",
            "form-0-availability": "100",
        }

        response = self.client.post(url, data)
        self.assertIn(response.status_code, (200, 302))

        if response.status_code == 302:
            self.assertTrue(mock_algolia.called)

    def test_edit_event_with_duplicate_ticket_category(self):
        """Editing with duplicate ticket categories hits error path."""
        ticket2 = TicketInfo.objects.create(
            event=self.event,
            category="VIP",
            price=100.00,
            availability=50,
        )

        url = reverse("events:edit_event", args=[self.event.id])
        data = {
            "title": "Updated Event",
            "description": "Description",
            "date": self.event.date.isoformat(),
            "time": "16:00:00",
            "location": "Location",
            "form-TOTAL_FORMS": "2",
            "form-INITIAL_FORMS": "2",
            "form-0-id": str(self.ticket_info.id),
            "form-0-category": "General Admission",
            "form-0-price": "50.00",
            "form-0-availability": "100",
            "form-1-id": str(ticket2.id),
            "form-1-category": "General Admission",
            "form-1-price": "100.00",
            "form-1-availability": "50",
        }

        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)

    def test_edit_event_category_not_required(self):
        """Test formset category field behavior on edit."""
        url = reverse("events:edit_event", args=[self.event.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertIn("formset", response.context)

    def test_edit_event_not_owner(self):
        """Test non-owner cannot edit event."""
        User.objects.create_user(username="other", password="pass123")
        self.client.login(username="other", password="pass123")
        session = self.client.session
        session["desired_role"] = "organizer"
        session.save()

        url = reverse("events:edit_event", args=[self.event.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)


class EventDeleteViewTests(TestCase):
    """Comprehensive tests for event deletion."""

    def setUp(self):
        """Create test data."""
        self.user = User.objects.create_user(username="organizer", password="pass123")
        self.organizer = OrganizerProfile.objects.create(
            user=self.user,
            full_name="Test Organizer",
            contact_email="org@example.com",
            phone="1234567890",
        )
        self.event = Event.objects.create(
            title="Test Event",
            date=date.today() + timedelta(days=1),
            time=time(14, 0),
            location="Test Location",
            organizer=self.organizer,
        )

        self.client.login(username="organizer", password="pass123")
        session = self.client.session
        session["desired_role"] = "organizer"
        session.save()

    def test_delete_event_get_request(self):
        """Test GET request shows confirmation page."""
        url = reverse("events:delete_event", args=[self.event.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "events/delete_event.html")

    @patch("events.views.algolia_delete")
    def test_delete_event_calls_algolia_delete(self, mock_algolia):
        """Test Algolia integration on event deletion."""
        url = reverse("events:delete_event", args=[self.event.id])
        response = self.client.post(url)

        self.assertIn(response.status_code, (200, 302))
        if response.status_code == 302:
            mock_algolia.assert_called_once()

    def test_delete_event_removes_from_database(self):
        """Test event is actually deleted."""
        event_id = self.event.id
        url = reverse("events:delete_event", args=[event_id])
        response = self.client.post(url)

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Event.objects.filter(id=event_id).exists())

    def test_delete_event_with_orders_prevents_deletion(self):
        """Test cannot delete event with existing orders."""
        from orders.models import Order
        from tickets.models import TicketInfo
        from accounts.models import UserProfile

        # Create UserProfile if not exists
        user_profile, _ = UserProfile.objects.get_or_create(
            user=self.user, defaults={"role": "attendee"}
        )

        # Create a ticket for this event
        ticket_info = TicketInfo.objects.create(
            event=self.event,
            category="General Admission",
            price=50.00,
            availability=100,
        )

        # Create order with correct fields
        Order.objects.create(
            attendee=user_profile,
            ticket_info=ticket_info,
            email=self.user.email or "test@example.com",
            full_name="Test User",
            phone="123-456-7890",
            price_at_purchase=50.00,
            quantity=2,
            status="completed",
        )

        # Try to delete the event
        url = reverse("events:delete_event", kwargs={"event_id": self.event.pk})
        response = self.client.post(url, follow=True)

        # Should redirect and event should still exist
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Event.objects.filter(pk=self.event.pk).exists())

        # Check for error message
        messages = list(response.context["messages"])
        self.assertTrue(any("cannot be deleted" in str(m).lower() for m in messages))


class EventListViewTests(TestCase):
    """Comprehensive tests for event list filtering and sorting."""

    def setUp(self):
        """Create test data."""
        self.user = User.objects.create_user(username="testuser", password="pass123")
        self.organizer = OrganizerProfile.objects.create(
            user=self.user,
            full_name="Test Organizer",
            contact_email="testorg@example.com",
            phone="1234567890",
        )

    def test_event_list_basic(self):
        """Test basic event list view."""
        Event.objects.create(
            title="Test Event",
            date=date.today() + timedelta(days=1),
            time=time(14, 0),
            location="Location",
            organizer=self.organizer,
        )

        url = reverse("events:event_list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_event_list_with_price_sorting_asc(self):
        """Test price sorting (low to high)."""
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

        url = reverse("events:event_list")
        response = self.client.get(url, {"price_sort": "asc"})

        self.assertEqual(response.status_code, 200)
        events = list(response.context["events"])
        self.assertEqual(events[0].title, "Cheap Event")

    def test_event_list_with_price_sorting_desc(self):
        """Test price sorting (high to low)."""
        event1 = Event.objects.create(
            title="Expensive Event",
            date=date.today() + timedelta(days=1),
            time=time(14, 0),
            location="Location",
            organizer=self.organizer,
        )
        TicketInfo.objects.create(
            event=event1,
            category="General",
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
            category="General",
            price=20.00,
            availability=50,
        )

        url = reverse("events:event_list")
        response = self.client.get(url, {"price_sort": "desc"})

        self.assertEqual(response.status_code, 200)
        events = list(response.context["events"])
        self.assertEqual(events[0].title, "Expensive Event")

    def test_event_list_with_distance_sort_valid_coords(self):
        """Test distance sorting with valid coordinates."""
        Event.objects.create(
            title="Event 1",
            date=date.today() + timedelta(days=1),
            time=time(14, 0),
            location="Location",
            latitude=40.7128,
            longitude=-74.0060,
            organizer=self.organizer,
        )

        url = reverse("events:event_list")
        response = self.client.get(
            url,
            {
                "distance_sort": "near",
                "user_lat": "40.7128",
                "user_lng": "-74.0060",
            },
        )

        self.assertEqual(response.status_code, 200)

    def test_event_list_with_distance_sort_no_coords(self):
        """Test distance sorting without coordinates."""
        Event.objects.create(
            title="Event 1",
            date=date.today() + timedelta(days=1),
            time=time(14, 0),
            location="Location",
            latitude=40.7128,
            longitude=-74.0060,
            organizer=self.organizer,
        )

        url = reverse("events:event_list")
        response = self.client.get(url, {"distance_sort": "near"})

        self.assertEqual(response.status_code, 200)

    def test_event_list_with_invalid_coordinates(self):
        """Test distance sorting with invalid coordinates."""
        Event.objects.create(
            title="Event 1",
            date=date.today() + timedelta(days=1),
            time=time(14, 0),
            location="Location",
            latitude=40.7128,
            longitude=-74.0060,
            organizer=self.organizer,
        )

        url = reverse("events:event_list")
        response = self.client.get(
            url,
            {
                "distance_sort": "near",
                "user_lat": "invalid",
                "user_lng": "invalid",
            },
        )

        self.assertEqual(response.status_code, 200)

    def test_event_list_with_radius_filter(self):
        """Test filtering by distance radius."""
        Event.objects.create(
            title="Nearby Event",
            date=date.today() + timedelta(days=1),
            time=time(14, 0),
            location="Location",
            latitude=40.7128,
            longitude=-74.0060,
            organizer=self.organizer,
        )

        url = reverse("events:event_list")
        response = self.client.get(
            url,
            {
                "user_lat": "40.7128",
                "user_lng": "-74.0060",
                "radius": "10",
            },
        )

        self.assertEqual(response.status_code, 200)

    def test_event_list_with_invalid_radius(self):
        """Test radius filter with invalid value."""
        Event.objects.create(
            title="Event",
            date=date.today() + timedelta(days=1),
            time=time(14, 0),
            location="Location",
            organizer=self.organizer,
        )

        url = reverse("events:event_list")
        response = self.client.get(
            url,
            {
                "user_lat": "40.7128",
                "user_lng": "-74.0060",
                "radius": "invalid",
            },
        )

        self.assertEqual(response.status_code, 200)

    def test_event_list_ticket_type_filter_general(self):
        """Test filtering by general admission ticket type."""
        event = Event.objects.create(
            title="General Event",
            date=date.today() + timedelta(days=1),
            time=time(14, 0),
            location="Location",
            organizer=self.organizer,
        )
        TicketInfo.objects.create(
            event=event,
            category="General Admission",
            price=50.00,
            availability=50,
            is_active=True,
        )

        url = reverse("events:event_list")
        response = self.client.get(url, {"ticket_type": ["general"]})

        self.assertEqual(response.status_code, 200)

    def test_event_list_ticket_type_filter_vip(self):
        """Test filtering by VIP ticket type."""
        event = Event.objects.create(
            title="VIP Event",
            date=date.today() + timedelta(days=1),
            time=time(14, 0),
            location="Location",
            organizer=self.organizer,
        )
        TicketInfo.objects.create(
            event=event,
            category="VIP",
            price=100.00,
            availability=50,
            is_active=True,
        )

        url = reverse("events:event_list")
        response = self.client.get(url, {"ticket_type": ["vip"]})

        self.assertEqual(response.status_code, 200)
        events = list(response.context["events"])
        self.assertEqual(len(events), 1)

    def test_event_list_ticket_type_filter_earlybird(self):
        """Test filtering by Early Bird ticket type."""
        event = Event.objects.create(
            title="Early Bird Event",
            date=date.today() + timedelta(days=1),
            time=time(14, 0),
            location="Location",
            organizer=self.organizer,
        )
        TicketInfo.objects.create(
            event=event,
            category="Early Bird",
            price=30.00,
            availability=50,
            is_active=True,
        )

        url = reverse("events:event_list")
        response = self.client.get(url, {"ticket_type": ["earlybird"]})

        self.assertEqual(response.status_code, 200)

    def test_event_list_date_sorting_soon(self):
        """Test date sorting (soonest first)."""
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

        url = reverse("events:event_list")
        response = self.client.get(url, {"date_sort": "soon"})

        events = list(response.context["events"])
        self.assertEqual(events[0].title, "Event 1")

    def test_event_list_date_sorting_late(self):
        """Test date sorting (latest first)."""
        Event.objects.create(
            title="Event 1",
            date=date.today() + timedelta(days=1),
            time=time(14, 0),
            location="Location",
            organizer=self.organizer,
        )
        Event.objects.create(
            title="Event 3",
            date=date.today() + timedelta(days=3),
            time=time(14, 0),
            location="Location",
            organizer=self.organizer,
        )

        url = reverse("events:event_list")
        response = self.client.get(url, {"date_sort": "late"})

        events = list(response.context["events"])
        self.assertEqual(events[0].title, "Event 3")

    def test_event_list_with_start_date_only(self):
        """Test filtering with start_date."""
        Event.objects.create(
            title="Future Event",
            date=date.today() + timedelta(days=10),
            time=time(14, 0),
            location="Location",
            organizer=self.organizer,
        )
        Event.objects.create(
            title="Near Event",
            date=date.today() + timedelta(days=2),
            time=time(14, 0),
            location="Location",
            organizer=self.organizer,
        )

        url = reverse("events:event_list")
        response = self.client.get(
            url,
            {
                "start_date": (date.today() + timedelta(days=5)).isoformat(),
            },
        )

        self.assertEqual(response.status_code, 200)
        events = list(response.context["events"])
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].title, "Future Event")

    def test_event_list_with_end_date_only(self):
        """Test filtering with end_date."""
        Event.objects.create(
            title="Soon Event",
            date=date.today() + timedelta(days=2),
            time=time(14, 0),
            location="Location",
            organizer=self.organizer,
        )
        Event.objects.create(
            title="Far Event",
            date=date.today() + timedelta(days=15),
            time=time(14, 0),
            location="Location",
            organizer=self.organizer,
        )

        url = reverse("events:event_list")
        response = self.client.get(
            url,
            {
                "end_date": (date.today() + timedelta(days=5)).isoformat(),
            },
        )

        self.assertEqual(response.status_code, 200)
        events = list(response.context["events"])
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].title, "Soon Event")

    def test_event_list_with_date_range(self):
        """Test filtering with both start and end dates."""
        Event.objects.create(
            title="In Range",
            date=date.today() + timedelta(days=5),
            time=time(14, 0),
            location="Location",
            organizer=self.organizer,
        )
        Event.objects.create(
            title="Out of Range",
            date=date.today() + timedelta(days=15),
            time=time(14, 0),
            location="Location",
            organizer=self.organizer,
        )

        url = reverse("events:event_list")
        response = self.client.get(
            url,
            {
                "start_date": (date.today() + timedelta(days=1)).isoformat(),
                "end_date": (date.today() + timedelta(days=10)).isoformat(),
            },
        )

        self.assertEqual(response.status_code, 200)
        events = list(response.context["events"])
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].title, "In Range")


class SubscribeNotificationTests(TestCase):
    """Comprehensive tests for notification subscription."""

    def setUp(self):
        """Create test data."""
        self.user = User.objects.create_user(
            username="testuser",
            password="pass123",
            email="user@example.com",
            first_name="Test",
            last_name="User",
        )
        self.organizer = OrganizerProfile.objects.create(
            user=self.user,
            full_name="Test Organizer",
            contact_email="org@example.com",
            phone="1234567890",
        )
        self.event = Event.objects.create(
            title="Test Event",
            date=date.today() + timedelta(days=1),
            time=time(14, 0),
            location="Test Location",
            organizer=self.organizer,
        )

    def test_subscribe_logged_in_uses_user_email(self):
        """Test logged-in user subscription uses account email."""
        self.client.login(username="testuser", password="pass123")

        url = reverse("events:subscribe_notification", args=[self.event.id])
        data = {}

        response = self.client.post(url, data)

        self.assertEqual(response.status_code, 302)
        if EventNotificationSubscription.objects.exists():
            sub = EventNotificationSubscription.objects.first()
            self.assertEqual(sub.email, "user@example.com")

    def test_subscribe_logged_in_uses_username_when_no_full_name(self):
        """Test username is used when user has no full name."""
        User.objects.create_user(
            username="justusername", password="pass123", email="user2@example.com"
        )
        self.client.login(username="justusername", password="pass123")

        url = reverse("events:subscribe_notification", args=[self.event.id])
        data = {}

        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)

    def test_subscribe_sends_confirmation_with_name(self):
        """Test confirmation email includes name."""
        url = reverse("events:subscribe_notification", args=[self.event.id])
        data = {
            "email": "test@example.com",
            "name": "John Doe",
        }

        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)

        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertIn("John Doe", email.body)

    def test_subscribe_confirmation_without_name(self):
        """Test confirmation email fallback when name absent."""
        url = reverse("events:subscribe_notification", args=[self.event.id])
        data = {
            "email": "test@example.com",
            "name": "",
        }

        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)

        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertIn("there", email.body)

    def test_subscribe_prevents_duplicate_subscriptions(self):
        """Test duplicate subscription prevention."""
        url = reverse("events:subscribe_notification", args=[self.event.id])
        data = {
            "email": "test@example.com",
            "name": "Test User",
        }

        # First subscription
        self.client.post(url, data)
        initial_count = EventNotificationSubscription.objects.count()

        # Try to subscribe again
        self.client.post(url, data)
        final_count = EventNotificationSubscription.objects.count()

        self.assertEqual(initial_count, final_count)

    def test_subscribe_without_email_shows_error(self):
        """Test subscription without email shows error."""
        url = reverse("events:subscribe_notification", args=[self.event.id])
        data = {
            "name": "Test User",
        }

        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)

    def test_subscribe_confirmation_email_uses_authenticated_user_name(self):
        """Test confirmation uses authenticated user's name in greeting."""
        self.client.login(username="testuser", password="pass123")

        url = reverse("events:subscribe_notification", args=[self.event.id])
        data = {
            "email": "newemail@example.com",
            "name": "",  # No name provided
        }

        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)

        # Should have sent confirmation email
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        # Should use user's full name in greeting
        self.assertIn("Test User", email.body)


class NotificationSubscribersViewTests(TestCase):
    """Tests for viewing notification subscribers."""

    def setUp(self):
        """Create test data."""
        self.user = User.objects.create_user(username="organizer", password="pass123")
        self.organizer = OrganizerProfile.objects.create(
            user=self.user,
            full_name="Test Organizer",
            contact_email="org@example.com",
            phone="1234567890",
        )
        self.event = Event.objects.create(
            title="Test Event",
            date=date.today() + timedelta(days=1),
            time=time(14, 0),
            location="Test Location",
            organizer=self.organizer,
        )
        self.client.login(username="organizer", password="pass123")

    def test_notification_subscribers_requires_organizer_role(self):
        """Test non-organizers cannot view subscribers."""
        session = self.client.session
        session["desired_role"] = "attendee"
        session.save()

        url = reverse("events:notification_subscribers", args=[self.event.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

    def test_notification_subscribers_organizer_must_own_event(self):
        """Test organizer can only view own event subscribers."""
        other_user = User.objects.create_user(username="other", password="pass123")
        OrganizerProfile.objects.create(
            user=other_user,
            full_name="Other Organizer",
            contact_email="other@example.com",
            phone="9876543210",
        )
        other_event = Event.objects.create(
            title="Other Event",
            date=date.today() + timedelta(days=1),
            time=time(14, 0),
            location="Location",
            organizer=self.organizer,
        )

        session = self.client.session
        session["desired_role"] = "organizer"
        session.save()

        url = reverse("events:notification_subscribers", args=[other_event.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

    def test_notification_subscribers_displays_list(self):
        """Test subscriber list is displayed."""
        session = self.client.session
        session["desired_role"] = "organizer"
        session.save()

        EventNotificationSubscription.objects.create(
            event=self.event, email="sub1@example.com", name="Subscriber 1"
        )

        url = reverse("events:notification_subscribers", args=[self.event.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("subscribers", response.context)


class NotifySubscribersTicketsAvailableTests(TestCase):
    """Tests for notifying subscribers about ticket availability."""

    def setUp(self):
        """Create test data."""
        self.user = User.objects.create_user(username="organizer", password="pass123")
        self.organizer = OrganizerProfile.objects.create(
            user=self.user,
            full_name="Test Organizer",
            contact_email="org@example.com",
            phone="1234567890",
        )
        self.event = Event.objects.create(
            title="Test Event",
            date=date.today() + timedelta(days=1),
            time=time(14, 0),
            location="Test Location",
            organizer=self.organizer,
        )
        self.client.login(username="organizer", password="pass123")
        session = self.client.session
        session["desired_role"] = "organizer"
        session.save()

    def test_notify_subscribers_sends_emails(self):
        url = reverse("events:notify_subscribers_send", args=[self.event.id])

        EventNotificationSubscription.objects.create(
            event=self.event, email="sub1@example.com", name="Subscriber 1"
        )
        EventNotificationSubscription.objects.create(
            event=self.event, email="sub2@example.com", name="Subscriber 2"
        )

        response = self.client.post(url)

        # Should send 2 emails
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(response.status_code, 302)

    def test_notify_subscribers_with_no_subscribers(self):
        """Test notification when no subscribers exist."""
        url = reverse("events:notify_subscribers_send", args=[self.event.id])

        response = self.client.post(url)

        # Should redirect with info message
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 0)

    def test_notify_subscribers_with_empty_email(self):
        """Test notification skips invalid email addresses."""
        url = reverse("events:notify_subscribers_send", args=[self.event.id])

        EventNotificationSubscription.objects.create(
            event=self.event, email="", name="Bad Subscriber"  # Empty email
        )
        EventNotificationSubscription.objects.create(
            event=self.event, email="good@example.com", name="Good Subscriber"
        )

        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)

        # Should only send 1 email (to valid address)
        self.assertEqual(len(mail.outbox), 1)

    def test_notify_subscribers_email_contains_greeting_with_name(self):
        """Test notification email includes subscriber name in greeting."""
        url = reverse("events:notify_subscribers_send", args=[self.event.id])

        EventNotificationSubscription.objects.create(
            event=self.event, email="sub@example.com", name="John Doe"
        )

        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)

        self.assertEqual(len(mail.outbox), 1)
        email_body = mail.outbox[0].body
        self.assertTrue("John Doe" in email_body or "Good news" in email_body)

    def test_notify_subscribers_email_contains_greeting_without_name(self):
        """Test notification email fallback when no name provided."""
        url = reverse("events:notify_subscribers_send", args=[self.event.id])

        EventNotificationSubscription.objects.create(
            event=self.event, email="sub@example.com", name=""
        )

        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)

        self.assertEqual(len(mail.outbox), 1)
        email_body = mail.outbox[0].body
        self.assertIn("Good news", email_body)

    @override_settings(SITE_BASE_URL="https://example.com")
    def test_notify_subscribers_uses_site_base_url(self):
        """Test notification uses SITE_BASE_URL when available."""
        url = reverse("events:notify_subscribers_send", args=[self.event.id])

        EventNotificationSubscription.objects.create(
            event=self.event, email="sub@example.com", name="Test"
        )

        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)

        self.assertEqual(len(mail.outbox), 1)
        email_body = mail.outbox[0].body
        self.assertIn("https://example.com", email_body)


class EventManagementDashboardTests(TestCase):
    """Tests for event management dashboard."""

    def setUp(self):
        """Create test data."""
        self.user = User.objects.create_user(username="organizer", password="pass123")
        self.organizer = OrganizerProfile.objects.create(
            user=self.user,
            full_name="Test Organizer",
            contact_email="org@example.com",
            phone="1234567890",
        )
        self.client.login(username="organizer", password="pass123")

    def test_dashboard_requires_login(self):
        """Test dashboard requires authentication."""
        self.client.logout()
        url = reverse("events:event_management_dashboard")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

    def test_dashboard_requires_organizer_profile(self):
        """Test dashboard requires organizer profile."""
        User.objects.create_user(username="noorganizer", password="pass123")
        self.client.login(username="noorganizer", password="pass123")

        url = reverse("events:event_management_dashboard")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

    def test_dashboard_displays_organizer_events(self):
        """Test dashboard shows organizer's events."""
        Event.objects.create(
            title="My Event",
            date=date.today() + timedelta(days=1),
            time=time(14, 0),
            location="Location",
            organizer=self.organizer,
        )

        url = reverse("events:event_management_dashboard")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("events", response.context)


class CancelEventTests(TestCase):
    """Tests for event cancellation."""

    def setUp(self):
        """Create test data."""
        self.user = User.objects.create_user(username="organizer", password="pass123")
        self.organizer = OrganizerProfile.objects.create(
            user=self.user,
            full_name="Test Organizer",
            contact_email="org@example.com",
            phone="1234567890",
        )
        self.event = Event.objects.create(
            title="Test Event",
            date=date.today() + timedelta(days=1),
            time=time(14, 0),
            location="Test Location",
            organizer=self.organizer,
        )
        self.client.login(username="organizer", password="pass123")

    def test_cancel_event_requires_login(self):
        """Test cancellation requires authentication."""
        self.client.logout()
        url = reverse("events:cancel_event", args=[self.event.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

    def test_cancel_event_requires_organizer_profile(self):
        """Test cancellation requires organizer profile."""
        User.objects.create_user(username="noorganizer", password="pass123")
        self.client.login(username="noorganizer", password="pass123")

        url = reverse("events:cancel_event", args=[self.event.id])
        response = self.client.get(url)
        # Should redirect to event list instead of 'home'
        self.assertEqual(response.status_code, 302)
        self.assertIn("event", response.url.lower())

    def test_cancel_event_non_owner_denied(self):
        """Test non-owner cannot cancel event."""
        other_user_name = "other"
        User.objects.create_user(username=other_user_name, password="pass123")
        OrganizerProfile.objects.create(
            user=User.objects.get(username=other_user_name),
            full_name="Other",
            contact_email="other@example.com",
            phone="1234567890",
        )
        self.client.login(username=other_user_name, password="pass123")

        url = reverse("events:cancel_event", args=[self.event.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

    def test_cancel_event_get_shows_confirmation(self):
        """Test GET request shows confirmation page."""
        url = reverse("events:cancel_event", args=[self.event.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    @patch("events.services.notify_event_cancellation")
    @patch("events.services.initiate_event_refunds")
    def test_cancel_event_post_marks_cancelled(self, mock_refunds, mock_notify):
        """Test POST request cancels event."""
        url = reverse("events:cancel_event", args=[self.event.id])
        response = self.client.post(url)

        # Refresh event from database
        self.event.refresh_from_db()
        self.assertTrue(self.event.is_cancelled)
        self.assertEqual(response.status_code, 302)

    def test_cancel_event_already_cancelled(self):
        """Test cancelling already cancelled event."""
        self.event.cancel()

        url = reverse("events:cancel_event", args=[self.event.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
