from django.db import models

from events.models import Event
from accounts.models import OrganizerProfile, UserProfile

# Create your models here.


class TicketInfo(models.Model):
    organizer = models.ForeignKey(OrganizerProfile, on_delete=models.CASCADE, related_name="distributes", null=True)
    CATEGORY_CHOICES = [
        ('General Admission', 'General Admission'),
        ('VIP', 'VIP'),
        ('Early Bird', 'Early Bird'),
    ]
    event = models.ForeignKey(Event, related_name='ticketInfo', on_delete=models.CASCADE)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    price = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    availability = models.IntegerField(default=0)

    class Meta:
        unique_together = ('event', 'category')

    def __str__(self):
        return f"{self.event.title} - {self.category}"


class Ticket(models.Model):
    attendee = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name="holds", null=True)
    ticketInfo = models.ForeignKey(TicketInfo, on_delete=models.CASCADE, related_name="lists", null=True)

    full_name = models.CharField(max_length=120, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)

    def __str__(self):
        return f"{self.event.title} - {self.category} - {self.attendee.user}"

