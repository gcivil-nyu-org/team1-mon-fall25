from django.shortcuts import get_object_or_404, render, redirect

from accounts.models import UserProfile
from .models import Ticket, TicketInfo
import json
from django.views.decorators.csrf import csrf_exempt
from . import services
from django.http import JsonResponse, HttpResponseNotAllowed, Http404

from django.contrib.auth.decorators import login_required
import base64
from io import BytesIO
import qrcode
from django.contrib import messages
from django.views.decorators.http import require_POST
from .services import build_tickets_pdf, send_ticket_email
from django.urls import reverse_lazy
from django.db.models import Q


def index(request):
    return render(request, "tickets/index.html")


@login_required(login_url=reverse_lazy("accounts:login"))
def details(request, id):
    """
    Show ticket details for the current user.

    If the ticket doesn't exist OR doesn't belong to this user,
    raise 404 (as tests expect).
    """
    attendee = UserProfile.objects.filter(user=request.user).first()
    if attendee is None:
        raise Http404("Ticket not found.")

    ticket = (
        Ticket.objects.filter(id=id, attendee=attendee)
        .select_related("ticketInfo__event")
        .first()
    )

    if ticket is None:
        raise Http404("Ticket not found.")

    event = ticket.ticketInfo.event
    qr_data_url = _qr_data_url_for_ticket(ticket)

    return render(
        request,
        "tickets/ticket_details.html",
        {"event": event, "ticket": ticket, "qr_data_url": qr_data_url},
    )


@login_required(login_url=reverse_lazy("accounts:login"))
def ticket_list(request):
    """
    For attendees: show their tickets.

    For current-role organizers: show an informational message and no tickets.
    """
    is_organizer = request.session.get("desired_role") == "organizer"

    if is_organizer:
        messages.info(
            request,
            (
                "Organizer accounts cannot purchase tickets. "
                "Please log in with an attendee account to buy tickets."
            ),
        )
        return render(
            request,
            "tickets/ticket_list.html",
            {
                "filtername": str(request.user),
                "tickets": [],
                "is_organizer": True,
            },
        )

    # Attendee view
    profile = UserProfile.objects.filter(user=request.user).first()

    qs = Ticket.objects.select_related("ticketInfo__event")

    filters = Q()
    if profile is not None:
        filters |= Q(attendee=profile)
    if request.user.email:
        filters |= Q(email__iexact=request.user.email)

    tickets = qs.filter(filters).order_by("-id").distinct()

    return render(
        request,
        "tickets/ticket_list.html",
        {
            "filtername": str(request.user),
            "tickets": tickets,
            "is_organizer": False,
        },
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


def _user_owns_tickets(user, tickets):
    """
    Returns True if the given user is allowed to see these tickets.
    A user 'owns' tickets if:
      - they are the attendee (UserProfile) OR
      - the ticket email matches their account email.
    """
    if not user.is_authenticated:
        return False

    profile = UserProfile.objects.filter(user=user).first()

    for t in tickets:
        if profile is not None and t.attendee_id == profile.id:
            return True
        if t.email and user.email and t.email.lower() == user.email.lower():
            return True

    return False


def ticket_thank_you(request, order_id):
    """
    Show a modern confirmation page after payment:
    - order number
    - email we sent tickets to
    - event info
    - primary ticket QR code
    - 'resend tickets' button

    If the user is authenticated and does NOT own the tickets,
    redirect them to their ticket list. Anonymous users are allowed
    (tests expect 200/404 without login).
    """
    tickets = list(
        Ticket.objects.filter(order_id=order_id)
        .select_related("ticketInfo__event")
        .order_by("id")
    )

    if not tickets:
        raise Http404("No tickets found for this order.")

    if request.user.is_authenticated and not _user_owns_tickets(request.user, tickets):
        messages.error(request, "You do not have access to that order.")
        return redirect("tickets:ticket_list")

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

    Tests call this without login; when there are tickets, they expect
    a redirect to the thank-you page. If the current user is logged in
    and does NOT own the tickets, we block it.
    """
    tickets = list(
        Ticket.objects.filter(order_id=order_id).select_related("ticketInfo__event")
    )

    if not tickets:
        messages.error(request, "We couldn't find any tickets for that order.")
        return redirect("tickets:ticket_thank_you", order_id=order_id)

    if request.user.is_authenticated and not _user_owns_tickets(request.user, tickets):
        messages.error(request, "You do not have permission to resend those tickets.")
        return redirect("tickets:ticket_list")

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
