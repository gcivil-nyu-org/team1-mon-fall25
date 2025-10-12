from django.db import models
from django.conf import settings

# Create your models here.


class OrganizerProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='organizer_profile')

    full_name = models.CharField(max_length=150, blank=True)
    contact_email = models.EmailField(blank=True)
    phone_number = models.CharField(max_length=30, blank=True)

    profile_photo = models.ImageField(upload_to='profiles/', blank=True, null=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.full_name or self.user.username
