# tickets/services.py
from io import BytesIO

from django.core.mail import EmailMessage
from django.utils import timezone

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
    Build a PDF containing the given tickets.

    - One ticket per page.
    - Event details on the left, attendee details on the right (single card).
    - QR code large and centered at the bottom.
    - Uses reportlab + qrcode if available; otherwise returns None so the
      email can still send without an attachment.
    """
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.platypus import (
            SimpleDocTemplate,
            Paragraph,
            Spacer,
            Table,
            TableStyle,
            Image,
            PageBreak,
        )
        import qrcode
    except ImportError:
        return None

    if not tickets:
        return None

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        title="Tickets",
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )

    styles = getSampleStyleSheet()
    elements = []

    for index, ticket in enumerate(tickets):
        event = ticket.ticketInfo.event if ticket.ticketInfo else None
        event_name = event.title if event else "Event"

        event_date = getattr(event, "date", None)
        event_time = getattr(event, "time", None)
        location = getattr(event, "location", "") if event else ""

        pretty_date = (
            event_date.strftime("%B %d, %Y") if event_date is not None else "TBD"
        )
        pretty_time = (
            event_time.strftime("%I:%M %p").lstrip("0")
            if event_time is not None
            else "TBD"
        )

        ticket_type = ticket.ticketInfo.category if ticket.ticketInfo else ""

        # ------------------------------------------------------------------
        # Header: event title + subtle ticket/order line
        # ------------------------------------------------------------------
        title_style = styles["Title"]
        title_style.textColor = colors.HexColor("#1A73E8")
        title = Paragraph(f"<b>{event_name}</b>", title_style)
        elements.append(title)

        # Nicer, single-line meta: “Ticket #18 · Order #12”
        meta_parts = [f"Ticket #{ticket.id}"]
        if ticket.order_id:
            meta_parts.append(f"Order #{ticket.order_id}")
        meta_line = " \u00b7 ".join(meta_parts)  # middle dot separator

        meta_p = Paragraph(
            f"<font size=10 color='#555555'>{meta_line}</font>",
            styles["Normal"],
        )
        elements.append(meta_p)
        elements.append(Spacer(1, 18))

        # ------------------------------------------------------------------
        # Two-column card: Event details (left) & Attendee info (right)
        # ------------------------------------------------------------------
        table_data = [
            # headers (span within each side)
            ["Event Details", "", "Attendee Information", ""],
            # row 1
            ["Date:", pretty_date, "Name:", ticket.full_name or "—"],
            # row 2
            ["Time:", pretty_time, "Email:", ticket.email or "—"],
            # row 3
            ["Location:", location or "—", "Ticket Type:", ticket_type or "—"],
        ]

        table = Table(
            table_data,
            colWidths=[1.0 * inch, 2.1 * inch, 1.2 * inch, 2.1 * inch],
        )

        table.setStyle(
            TableStyle(
                [
                    # span headers within each side
                    ("SPAN", (0, 0), (1, 0)),  # Event header
                    ("SPAN", (2, 0), (3, 0)),  # Attendee header
                    # header background
                    ("BACKGROUND", (0, 0), (1, 0), colors.HexColor("#F1F3F4")),
                    ("BACKGROUND", (2, 0), (3, 0), colors.HexColor("#F1F3F4")),
                    # header font
                    ("FONTNAME", (0, 0), (3, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (3, 0), 11),
                    ("ALIGN", (0, 0), (3, 0), "LEFT"),
                    # labels
                    ("FONTNAME", (0, 1), (0, 3), "Helvetica-Bold"),
                    ("FONTNAME", (2, 1), (2, 3), "Helvetica-Bold"),
                    ("ALIGN", (0, 1), (0, 3), "RIGHT"),
                    ("ALIGN", (2, 1), (2, 3), "RIGHT"),
                    # table box & grid
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("INNERGRID", (0, 1), (1, 3), 0.25, colors.lightgrey),
                    ("INNERGRID", (2, 1), (3, 3), 0.25, colors.lightgrey),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )

        elements.append(table)
        elements.append(Spacer(1, 32))

        # ------------------------------------------------------------------
        # QR code: big, centered
        # ------------------------------------------------------------------
        qr_value = ticket.qr_code or f"TICKET-{ticket.id}"
        qr = qrcode.QRCode(box_size=6, border=2)
        qr.add_data(qr_value)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white")

        img_buffer = BytesIO()
        qr_img.save(img_buffer, format="PNG")
        img_buffer.seek(0)

        qr_image = Image(img_buffer, width=2.5 * inch, height=2.5 * inch)
        qr_image.hAlign = "CENTER"
        elements.append(qr_image)
        elements.append(Spacer(1, 18))

        # ------------------------------------------------------------------
        # Footer note
        # ------------------------------------------------------------------
        footer = Paragraph(
            "<font size=9 color='#666666'>"
            "Please bring this ticket (or the QR code) to the event for entry.<br/>"
            "If you have any questions, please contact the event organizer."
            "</font>",
            styles["Normal"],
        )
        elements.append(footer)

        # Page break between tickets
        if index != len(tickets) - 1:
            elements.append(PageBreak())

    # Build the PDF
    doc.build(elements)
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
        (
            "Each ticket includes a unique QR code that you can present at the "
            "event entrance."
        ),
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
