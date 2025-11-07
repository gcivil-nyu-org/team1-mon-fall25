from django.shortcuts import get_object_or_404, render

from accounts.models import UserProfile
from events.models import Event
from .models import Ticket
import json
from django.views.decorators.csrf import csrf_exempt
from . import services
from .models import TicketInfo
from django.http import JsonResponse, HttpResponseNotAllowed

import base64
from io import BytesIO
import qrcode
from django.contrib import messages
from django.http import Http404
from django.views.decorators.http import require_POST
from .services import build_tickets_pdf, send_ticket_email


def index(request):
    return render(request, "tickets/index.html")


def details(request, id):
    ticket = get_object_or_404(Ticket, id=id)
    event = get_object_or_404(Event, id=ticket.ticketInfo.event.id)
    return render(
        request,
        "tickets/ticket_details.html",
        {"event": event, "ticket": ticket},
    )


def ticket_list(request):
    if request.session.get("desired_role") == "attendee":
        attendee = UserProfile.objects.get(user=request.user)
        filtername = str(attendee.user)
        tickets = Ticket.objects.filter(attendee=attendee)
    else:
        filtername = "all"
        tickets = Ticket.objects.all()

    return render(
        request,
        "tickets/ticket_list.html",
        {"filtername": filtername, "tickets": tickets},
    )


@csrf_exempt
def payment_confirm(request):
    """
    Endpoint to be called AFTER payment is confirmed (e.g. by Stripe success handler).
    Expected JSON body:
    {
        "order_id": "ch_123" or "sess_123" or your own id,
        "ticket_info_id": 5,
        "full_name": "John Doe",
        "email": "john@example.com",
        "phone": "1234567890"
    }

    This will:
    - create a Ticket
    - generate QR code
    - generate PDF (if reportlab installed)
    - send email with PDF attached
    """
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    try:
        data = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    order_id = data.get("order_id")
    ticket_info_id = data.get("ticket_info_id")
    full_name = data.get("full_name") or ""
    email = data.get("email") or ""
    phone = data.get("phone") or ""

    if not order_id or not ticket_info_id or not email:
        return JsonResponse(
            {"error": "order_id, ticket_info_id, and email are required"},
            status=400,
        )

    ticket_info = get_object_or_404(TicketInfo, id=ticket_info_id)

    # attendee is optional here because Stripe/webhooks won't be authenticated
    ticket = services.issue_ticket_for_order(
        order_id=order_id,
        ticket_info=ticket_info,
        full_name=full_name,
        email=email,
        phone=phone,
        attendee=None,
    )

    pdf_bytes = services.build_tickets_pdf([ticket])
    services.send_ticket_email(email, [ticket], pdf_bytes)

    return JsonResponse(
        {
            "status": "ok",
            "ticket_id": ticket.id,
            "order_id": ticket.order_id,
            "message": "Ticket issued and email sent.",
        },
        status=200,
    )

def _qr_data_url_for_ticket(ticket):
    """
    Build a data: URL PNG for the ticket's QR code.
    Safe to call multiple times; will generate qr_code if missing.
    """
    if not ticket.qr_code:
        ticket.ensure_qr()
        ticket.save(update_fields=["qr_code"])

    qr = qrcode.QRCode(box_size=8, border=2)
    qr.add_data(ticket.qr_code)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buffer = BytesIO()
    img.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"

def ticket_thank_you(request, order_id):
    """
    Show a modern confirmation page after payment:
    - order number
    - email we sent tickets to
    - event info
    - primary ticket QR code
    - 'resend tickets' button
    """
    tickets = (
        Ticket.objects
        .filter(order_id=order_id)
        .select_related("ticketInfo__event")
        .order_by("id")
    )

    if not tickets:
        raise Http404("No tickets found for this order.")

    primary = tickets[0]
    event = primary.ticketInfo.event if primary.ticketInfo else None

    qr_data_url = _qr_data_url_for_ticket(primary)

    context = {
        "order_id": order_id,
        "tickets": tickets,
        "primary_ticket": primary,
        "event": event,
        "qr_data_url": qr_data_url,
    }
    return render(request, "tickets/thank_you.html", context)

@require_POST
def ticket_resend(request, order_id):
    """
    Re-send ticket email (with PDF) for this order.
    Uses the same email + PDF logic as payment_confirm.
    """
    tickets = list(
        Ticket.objects
        .filter(order_id=order_id)
        .select_related("ticketInfo__event")
    )

    if not tickets:
        messages.error(request, "We couldn't find any tickets for that order.")
        return redirect("tickets:ticket_thank_you", order_id=order_id)

    email = tickets[0].email
    if not email:
        messages.error(
            request,
            "This order doesn't have an email address saved yet.",
        )
        return redirect("tickets:ticket_thank_you", order_id=order_id)

    pdf_bytes = build_tickets_pdf(tickets)
    send_ticket_email(email, tickets, pdf_bytes=pdf_bytes)

    messages.success(request, "We just re-sent your tickets to your inbox.")
    return redirect("tickets:ticket_thank_you", order_id=order_id)

