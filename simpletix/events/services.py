from typing import Iterable
import stripe
import os
from decimal import Decimal

from django.db import transaction
from django.conf import settings
from django.core.mail import send_mail

from .models import Event
from orders.models import Order
from tickets.models import Ticket


def get_event_orders(event: Event) -> Iterable[Order]:
    """
    Return the orders that belong to this event and are eligible
    for cancellation notifications & refunds.

    We use:
      Event -> TicketInfo (FK) -> Order (FK ticket_info)
    and filter on status="completed" to only target successful purchases.
    """
    return (
        Order.objects.filter(
            ticket_info__event=event, status__in=["completed", "partially_refunded"]
        )
        .select_related("ticket_info", "attendee__user", "billing_info")
        .order_by("created_at")
    )


def get_event_tickets_for_order_ids(event: Event, order_ids):
    """
    Optional helper: fetch tickets tied to this event and a set of order IDs.
    This can be useful for your teammate implementing refunds or
    ticket invalidation.
    """
    if not order_ids:
        return Ticket.objects.none()

    return Ticket.objects.filter(
        ticketInfo__event=event,
        order_id__in=order_ids,
    ).select_related("ticketInfo", "attendee__user")


def notify_event_cancellation(event: Event) -> None:
    """
    Send cancellation email to all attendees who bought tickets for this event.

    We use the Order's stored `email` (the one used at checkout), which is the
    most reliable contact point for refunds and notifications.
    """
    orders = get_event_orders(event)

    if not orders:
        return

    subject = f"Event Cancelled: {event.title}"

    # Keep this plain-text and simple; you can later swap to templates.
    base_message = (
        'We’re sorry to inform you that the event "{title}" scheduled for '
        "{date} at {time} has been cancelled by the organizer.\n\n"
        "A refund has been initiated for your ticket purchase. You will "
        "receive the refund soon based on your payment method.\n\n"
        "Thank you for your understanding.\n"
        "- SimpleTix Team"
    )

    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@example.com")

    for order in orders:
        # Prefer the name/email captured at checkout (Order)
        email = order.email
        if not email:
            # Fallbacks – in case something is missing
            if order.billing_info and order.billing_info.email:
                email = order.billing_info.email
            elif order.attendee and getattr(order.attendee, "user", None):
                email = order.attendee.user.email

        if not email:
            # No reachable email for this order — skip silently
            continue

        name = order.full_name or (
            order.billing_info.full_name if order.billing_info else ""
        )
        # Fallback to attendee.user if needed
        if not name and order.attendee and getattr(order.attendee, "user", None):
            name = order.attendee.user.get_full_name() or order.attendee.user.username

        greeting = f"Dear {name}," if name else "Dear attendee,"

        message = f"{greeting}\n\n" + base_message.format(
            title=event.title,
            date=event.date,  # rendered as YYYY-MM-DD by default
            time=event.time,  # time object; OK in plain text
        )

        send_mail(
            subject,
            message,
            from_email,
            [email],
            fail_silently=True,  # set to False locally if you want to debug
        )


def initiate_event_refunds(event: Event) -> None:
    """
    Initiates a full refund process for all completed orders of a cancelled event.
    Sets status to 'refund_processing'. The webhook handles final confirmation.
    """
    orders = get_event_orders(event)
    if not orders.exists():
        return

    # Ensure Stripe key is set
    stripe.api_key = settings.STRIPE.get("STRIPE_SECRET_KEY", "")

    for _order in orders:
        try:
            with transaction.atomic():
                # Lock the order row to prevent concurrent modifications
                order = Order.objects.select_for_update().get(id=_order.id)

                # Double-check status and session ID
                if (
                    order.status in ["completed", "partially_refunded"]
                    and order.stripe_session_id
                ):

                    # 1. Retrieve PaymentIntent
                    session = stripe.checkout.Session.retrieve(order.stripe_session_id)
                    payment_intent_id = session.payment_intent

                    if payment_intent_id:
                        refunded_so_far = order.amount_refunded or Decimal(0)
                        remaining_balance = order.total_price - refunded_so_far

                        # Skip if fully refunded (safeguard)
                        if remaining_balance <= 0:
                            continue

                        # Convert to cents
                        refund_amount_cents = int(remaining_balance * 100)

                        # 2. Create Refund in Stripe
                        # We use metadata so our webhook knows which order this is
                        stripe.Refund.create(
                            payment_intent=payment_intent_id,
                            amount=refund_amount_cents,
                            # 'duplicate' or 'fraudulent' are other options
                            reason="requested_by_customer",
                            metadata={
                                "order_id": order.id,
                                "environment": os.getenv("ENVIRONMENT", "development"),
                            },
                        )

                        # 3. Update Status
                        # We do NOT restock tickets here because the event is cancelled.
                        # We mark it as processing so the webhook sends the email.
                        order.status = "refund_processing"
                        order.save()

        except Exception as e:
            print(f"Failed to initiate auto-refund for order {_order.id}: {e}")
