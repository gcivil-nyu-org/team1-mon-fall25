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
    banner = models.ImageField(upload_to="banners/", blank=True, null=True)
    video = models.FileField(upload_to="event_videos/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title
