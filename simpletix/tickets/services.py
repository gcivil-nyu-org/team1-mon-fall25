# tickets/services.py
from django.utils import timezone
from .models import Ticket, TicketInfo
from django.core.mail import EmailMessage

def issue_ticket_for_order_id(order_id, ticket_info, full_name, email, phone, attendee=None):
    ticket = Ticket.objects.create(
        attendee=attendee,
        ticketInfo=ticket_info,
        full_name=full_name or "",
        email=email or "",
        phone=phone or "",
        order_id=order_id,
        status="ISSUED",
        issued_at=timezone.now(),
    )
    ticket.ensure_qr()
    ticket.save()
    return ticket

def send_ticket_email(to_email, tickets, pdf_bytes=None):
    if not to_email:
        return
    subject = "Your ticket"
    body = "Thank you for your purchase. Attached are your ticket details."
    msg = EmailMessage(subject, body, to=[to_email])
    if pdf_bytes:
        msg.attach("tickets.pdf", pdf_bytes, "application/pdf")
    msg.send(fail_silently=True)