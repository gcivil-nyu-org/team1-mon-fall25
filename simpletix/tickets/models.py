from django.db import models
import uuid

from events.models import Event
from accounts.models import OrganizerProfile, UserProfile


class TicketInfo(models.Model):
    organizer = models.ForeignKey(
        OrganizerProfile,
        on_delete=models.CASCADE,
        related_name="distributes",
        null=True,
    )
    CATEGORY_CHOICES = [
        ("General Admission", "General Admission"),
        ("VIP", "VIP"),
        ("Early Bird", "Early Bird"),
    ]
    event = models.ForeignKey(
        Event, related_name="ticketInfo", on_delete=models.CASCADE
    )
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    price = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    availability = models.IntegerField(default=0)

    class Meta:
        unique_together = ("event", "category")

    def __str__(self):
        return f"{self.event.title} - {self.category}"


class Ticket(models.Model):
    attendee = models.ForeignKey(
        UserProfile, on_delete=models.CASCADE, related_name="holds", null=True
    )

    ticketInfo = models.ForeignKey(
        TicketInfo, on_delete=models.CASCADE, related_name="lists", null=True
    )

    full_name = models.CharField(max_length=120, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)

    order_id = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        help_text="Group tickets that belong to the same checkout/payment.",
    )

    status = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text="PENDING / ISSUED / USED. Left null for legacy tickets.",
    )
    qr_code = models.CharField(
        max_length=160,
        blank=True,
        null=True,
        unique=True,
        help_text="QR payload or unique ticket code.",
    )
    issued_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        """
        Be defensive so we don't crash admin/templates
        if ticketInfo or attendee is missing.
        """
        base = f"Ticket #{self.pk}"
        pieces = [base]

        if self.ticketInfo:
            event_title = getattr(self.ticketInfo.event, "title", None)
            if event_title:
                pieces.append(f"for {event_title}")
            pieces.append(f"({self.ticketInfo.category})")

        # attendee can be null
        if self.attendee and getattr(self.attendee, "user", None):
            pieces.append(f"- {self.attendee.user}")

        return " ".join(pieces)

    def ensure_qr(self):
        """
        Helper: generate a QR/code only if missing.
        Safe to call from views/services without breaking old tickets.
        """
        if not self.qr_code:
            self.qr_code = f"TCKT-{uuid.uuid4().hex}"
