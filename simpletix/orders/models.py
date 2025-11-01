from django.db import models

from accounts.models import UserProfile
from tickets.models import TicketInfo

# Create your models here.



class BillingInfo(models.Model):
    # Store billing info (can be filled in by webhook or form)
    full_name = models.CharField(max_length=120, null=True, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)

    def __str__(self):
        return f"{self.full_name} - {self.email} - {self.phone}"

class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    attendee = models.ForeignKey(
        UserProfile, on_delete=models.CASCADE, related_name="places", null=True
    )

    # Link directly to the *type* of ticket being bought
    ticket_info = models.ForeignKey(
        TicketInfo, 
        on_delete=models.PROTECT, # Don't delete an order if the TicketInfo is deleted
        related_name="ticketInOrder"
    )

    # Link directly to the billing info
    billing_info = models.ForeignKey(
        BillingInfo, 
        on_delete=models.PROTECT, # Don't delete an order if the BillingInfo is deleted
        related_name="billingfor",
        null=True,
        blank=True
    )
    
    # Store attendee info
    full_name = models.CharField(max_length=120, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)

    # Order status and tracking
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    
    # Store the price at the time of purchase
    price_at_purchase = models.DecimalField(max_digits=8, decimal_places=2)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Store the Stripe ID for reconciliation
    stripe_session_id = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"Order {self.id} ({self.status}) - {self.ticket_info.category} for {self.full_name}"

    def save(self, *args, **kwargs):
        # Set the price automatically when the item is first created
        if not self.id:
            self.price_at_purchase = self.ticket_info.price
        super().save(*args, **kwargs)