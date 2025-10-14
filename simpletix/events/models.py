from django.db import models

class Event(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    date = models.DateField()
    time = models.TimeField()
    location = models.CharField(max_length=255)
    banner = models.ImageField(upload_to='banners/', blank=True, null=True)
    video = models.FileField(upload_to='event_videos/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    # 👇 Add these helper methods for Algolia
    @property
    def date_str(self):
        return self.date.isoformat() if self.date else None

    @property
    def time_str(self):
        return self.time.strftime("%H:%M:%S") if self.time else None




class Ticket(models.Model):
    CATEGORY_CHOICES = [
        ('general', 'General Admission'),
        ('vip', 'VIP'),
        ('earlybird', 'Early Bird'),
    ]
    event = models.ForeignKey(Event, related_name='tickets', on_delete=models.CASCADE)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    availability = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.event.title} - {self.category}"

