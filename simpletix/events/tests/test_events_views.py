from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from datetime import date, time, timedelta
from events.models import Event
from accounts.models import OrganizerProfile
from tickets.models import TicketInfo


class EventDetailViewTest(TestCase):
    def setUp(self):
        """Create test data for all tests."""
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
        # Trying to access a non-existent event should return 404
        response = self.client.get(reverse("events:event_detail", args=[999]))
        self.assertEqual(response.status_code, 404)

    def test_event_detail_view_loads_successfully(self):
        """Test that event detail view returns 200 for existing event."""
        url = reverse("events:event_detail", args=[self.event.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "events/event_detail.html")

    def test_event_detail_displays_correct_data(self):
        """Test that event detail shows correct information."""
        url = reverse("events:event_detail", args=[self.event.id])
        response = self.client.get(url)
        self.assertContains(response, "Test Event")
        self.assertContains(response, "Test Description")
        self.assertContains(response, "Test Location")

    def test_event_detail_with_sold_out_tickets(self):
        """Test event detail when tickets are sold out."""
        # Create ticket with no availability
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
        self.assertTrue(response.context['is_sold_out'])

    def test_event_detail_with_available_tickets(self):
        """Test event detail when tickets are available."""
        # Create ticket with availability
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
        self.assertFalse(response.context['is_sold_out'])

    def test_event_detail_subscriber_count(self):
        """Test that subscriber count is displayed correctly."""
        from events.models import EventNotificationSubscription
        
        # Create some subscribers
        EventNotificationSubscription.objects.create(
            event=self.event,
            email="sub1@example.com",
            name="Subscriber 1"
        )
        EventNotificationSubscription.objects.create(
            event=self.event,
            email="sub2@example.com",
            name="Subscriber 2"
        )
        
        url = reverse("events:event_detail", args=[self.event.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['subscriber_count'], 2)