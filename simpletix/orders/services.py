from django.core.mail import EmailMessage


def send_refund_email(order, refund_amount):
    """
    Send an email to the customer confirming their refund (full or partial).
    Includes Event and Organizer details.
    """
    if not order.email:
        return

    # Fetch Event and Organizer details
    event = order.ticket_info.event if order.ticket_info else None
    organizer = event.organizer if event else None

    event_name = event.title if event else "your event"

    # Determine refund status
    is_full_refund = order.status == "refunded"
    refund_type = "Full Refund" if is_full_refund else "Partial Refund"

    subject = f"{refund_type} Notification for {event_name} (Order #{order.id})"

    # Build the email body
    body_lines = [
        f"Hi {order.full_name or 'there'},",
        "",
        (
            "We are writing to let you know that a refund has been processed "
            f"for your order #{order.id}."
        ),
        "",
        "Refund Details:",
        "--------------------------------------------------",
        f"Refund Amount: ${refund_amount:,.2f}",
        f"Total Refunded to Date: ${order.amount_refunded:,.2f}",
        f"Original Order Total: ${order.total_price:,.2f}",
        "--------------------------------------------------",
        "",
    ]

    if is_full_refund:
        body_lines.append(
            (
                "This completes the refund for your order. "
                "Your order has been fully refunded."
            )
        )
    else:
        remaining_balance = order.total_price - order.amount_refunded
        body_lines.append(
            (
                "This is a partial refund. The remaining balance "
                f"on your order is ${remaining_balance:,.2f}."
            )
        )

    if event:
        body_lines.extend(
            [
                "",
                "Event Information:",
                "--------------------------------------------------",
                f"Event: {event.title}",
                f"Date: {event.date.strftime('%B %d, %Y')}",  # e.g. January 01, 2025
                f"Time: {event.time.strftime('%I:%M %p')}",  # e.g. 05:30 PM
                f"Location: {event.location}",
            ]
        )
        if event.formatted_address:
            body_lines.append(f"Address: {event.formatted_address}")
        body_lines.append("--------------------------------------------------")

    if organizer:
        body_lines.extend(
            [
                "",
                "Organizer Information:",
                "--------------------------------------------------",
                f"Name: {organizer.full_name or organizer.user.username}",
            ]
        )
        if organizer.contact_email:
            body_lines.append(f"Email: {organizer.contact_email}")
        if organizer.phone:
            body_lines.append(f"Phone: {organizer.phone}")
        body_lines.append("--------------------------------------------------")
        body_lines.append("")

    body_lines.extend(
        [
            (
                "The funds should appear on your statement "
                "within 5-10 business days, depending on your bank."
            ),
            "",
            (
                "If you have any questions, please contact "
                "the event organizer directly using the information above."
            ),
            "",
            "Best regards,",
            "SimpleTix Team",
        ]
    )

    body = "\n".join(body_lines)

    msg = EmailMessage(subject, body, to=[order.email])

    # Send securely
    msg.send(fail_silently=False)
