# tickets/services.py
from io import BytesIO
from django.utils import timezone
from django.core.mail import EmailMessage

from .models import Ticket, TicketInfo


def issue_ticket_for_order(
    *,
    order_id: str,
    ticket_info: TicketInfo,
    full_name: str,
    email: str,
    phone: str,
    attendee=None,
):
    """
    Create a Ticket after payment succeeds.
    Uses order_id (string) so we don't depend on the orders app yet.
    """
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

    # Decrement availability safely
    if (
        ticket_info
        and ticket_info.availability is not None
        and ticket_info.availability > 0
    ):
        ticket_info.availability -= 1
        ticket_info.save()

    return ticket


def build_tickets_pdf(tickets):
    """
    Build a PDF containing all given tickets, each with a QR code.

    If reportlab or qrcode are not installed, return None so that
    the email can still be sent without an attachment.
    """
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.lib.utils import ImageReader
        import qrcode
    except ImportError:
        return None

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    page_width, page_height = A4

    margin_x = 20 * mm
    margin_y = 20 * mm
    qr_size = 35 * mm

    y = page_height - margin_y
    pdf.setFont("Helvetica", 12)

    for ticket in tickets:
        event = ticket.ticketInfo.event if ticket.ticketInfo else None
        event_name = event.title if event else "Event"
        event_date = getattr(event, "start_time", "")

        # Header for this ticket
        pdf.drawString(margin_x, y, f"Ticket ID: {ticket.id}")
        y -= 16
        pdf.drawString(margin_x, y, f"Event: {event_name}")
        y -= 16
        pdf.drawString(margin_x, y, f"Date: {event_date}")
        y -= 16

        pdf.drawString(margin_x, y, f"Name: {ticket.full_name}")
        y -= 16
        pdf.drawString(margin_x, y, f"Email: {ticket.email}")
        y -= 16

        ticket_type = ticket.ticketInfo.category if ticket.ticketInfo else ""
        pdf.drawString(margin_x, y, f"Ticket Type: {ticket_type}")
        y -= 16

        # Generate QR code image from ticket.qr_code
        qr = qrcode.QRCode(box_size=4, border=2)
        qr.add_data(ticket.qr_code or "")
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white")

        img_buffer = BytesIO()
        qr_img.save(img_buffer, format="PNG")
        img_buffer.seek(0)

        qr_reader = ImageReader(img_buffer)

        # Position QR on the right side of the page
        qr_x = page_width - margin_x - qr_size
        qr_y = y - qr_size + 8  # small offset up

        pdf.drawImage(
            qr_reader,
            qr_x,
            qr_y,
            width=qr_size,
            height=qr_size,
        )

        img_buffer.close()

        # Leave some space before next ticket
        y -= qr_size + 24

        # New page if we are near the bottom
        if y < margin_y + qr_size:
            pdf.showPage()
            pdf.setFont("Helvetica", 12)
            y = page_height - margin_y

    pdf.showPage()
    pdf.save()

    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


def send_ticket_email(to_email, tickets, pdf_bytes=None):
    """
    Send the ticket email. PDF is optional (but we will pass it when available).
    """
    if not to_email:
        return

    first_ticket = tickets[0]
    event = first_ticket.ticketInfo.event if first_ticket.ticketInfo else None
    event_name = event.title if event else "your event"

    subject = f"Your tickets for {event_name}"
    body_lines = [
        f"Hi {first_ticket.full_name or 'there'},",
        "",
        (
            "Thank you for your purchase. Your ticket(s) are attached as a PDF "
            "with all the details you need."
        ),
        ("Each ticket includes a unique QR code that you can present at the " "event."),
        "",
        "If you have any questions, please contact the event organizer.",
        "",
        "Best regards,",
        "SimpleTix Team",
    ]
    body = "\n".join(body_lines)

    msg = EmailMessage(subject, body, to=[to_email])

    if pdf_bytes:
        msg.attach("tickets.pdf", pdf_bytes, "application/pdf")

    msg.send(fail_silently=False)
