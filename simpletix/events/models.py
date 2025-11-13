from django.db import models
from accounts.models import OrganizerProfile


class Event(models.Model):
    organizer = models.ForeignKey(
        OrganizerProfile, on_delete=models.CASCADE, related_name="creates", null=True
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

    def __str__(self):
        return self.title

    @property
    def date_str(self):
        """
        ISO-8601 string for Algolia / search.
        In normal app usage `self.date` is a DateField (has .isoformat()).
        In some tests it may be a plain string – we handle both.
        """
        value = self.date
        if not value:
            return None
        # Normal case: DateField / date-like object
        if hasattr(value, "isoformat"):
            return value.isoformat()
        # Fallback: already a string or something string-like
        return str(value)

    @property
    def time_str(self):
        """
        "HH:MM:SS" string for Algolia / search.
        In normal app usage `self.time` is a TimeField (has .strftime()).
        In some tests it may be a plain string – we handle both.
        """
        value = self.time
        if not value:
            return None
        # Normal case: TimeField / time-like object
        if hasattr(value, "strftime"):
            return value.strftime("%H:%M:%S")
        # Fallback: already a string or something string-like
        return str(value)

# NEW MODEL - Add this at the bottom
class EventTimeSlot(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='time_slots')
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['date', 'start_time']
    
    def __str__(self):
        return f"{self.event.title} - {self.date} {self.start_time}-{self.end_time}"