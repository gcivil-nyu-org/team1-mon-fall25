from django.db import models
from django.contrib.auth.models import User

# Create your models here.

ROLE_CHOICES = (
    ("organizer", "Organizer"),
    ("attendee", "Attendee"),
)


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="uprofile")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="attendee")

    def __str__(self):
        return f"{self.user.username} ({self.role})"


class OrganizerProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    full_name = models.CharField(max_length=120, blank=True)
    contact_email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    profile_photo = models.ImageField(
        upload_to="profile_photos/", blank=True, null=True
    )

    def __str__(self):
        return self.user.username
