from django.db import models
from accounts.models import OrganizerProfile
from django.contrib.auth.models import User  # Assuming attendees are Users


class Event(models.Model):
    organizer = models.ForeignKey(
        OrganizerProfile,
        on_delete=models.CASCADE,
        related_name="creates",
        null=True,
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    date = models.DateField()
    time = models.TimeField()
    location = models.CharField(max_length=255)

    formatted_address = models.CharField(max_length=255, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    banner = models.ImageField(upload_to="banners/", blank=True, null=True)
    video = models.FileField(upload_to="event_videos/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    manual_approval = models.BooleanField(default=False)
    waitlist_enabled = models.BooleanField(default=False)
    ticket_limit = models.PositiveIntegerField(
        default=100
    )  # optional, line broken to satisfy Flake8

    def __str__(self):
        return self.title

    @property
    def date_str(self):
        return self.date.isoformat() if self.date else None

    @property
    def time_str(self):
        return self.time.strftime("%H:%M:%S") if self.time else None


class Waitlist(models.Model):
    event = models.ForeignKey(
        Event, on_delete=models.CASCADE, related_name="waitlist_entries"
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    joined_at = models.DateTimeField(auto_now_add=True)
    is_approved = models.BooleanField(default=False)  # Organizer will manually approve

    def __str__(self):
        status = "Approved" if self.is_approved else "Pending"
        return f"{self.user.username} - {self.event.title} ({status})"
