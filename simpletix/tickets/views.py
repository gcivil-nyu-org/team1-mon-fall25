from django.shortcuts import get_object_or_404, render, redirect
from django.http import JsonResponse, HttpResponseNotAllowed, Http404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from django.contrib import messages
from django.db.models import Q

from accounts.models import UserProfile, OrganizerProfile
from .models import Ticket, TicketInfo
from . import services
from .services import build_tickets_pdf, send_ticket_email

import json
import base64
from io import BytesIO
import qrcode


def index(request):
    return render(request, "tickets/index.html")


def details(request, id):
    """
    Ticket details view.

    Behaviour:

    - If ticket does not exist at all → 404 with our ticket_not_found template.
    - If user is logged in AND does NOT own the ticket → 404 with the same template.
    - Otherwise (guest or rightful owner) → render ticket details (200).
    """

    # Look up the ticket (with event) or show our friendly 404 template
    ticket = Ticket.objects.select_related("ticketInfo__event").filter(id=id).first()
    if ticket is None:
        return render(
            request,
            "tickets/ticket_not_found.html",
            status=404,
        )

    # Ownership enforcement only for logged-in users
    if request.user.is_authenticated:
        profile = UserProfile.objects.filter(user=request.user).first()
        owns = False

        # Match by attendee profile
        if profile and ticket.attendee_id == profile.id:
            owns = True

        # Or match by email
        if (
            ticket.email
            and request.user.email
            and ticket.email.lower() == request.user.email.lower()
        ):
            owns = True

        if not owns:
            # Ticket exists but belongs to someone else → friendly 404
            return render(
                request,
                "tickets/ticket_not_found.html",
                status=404,
            )

    # At this point, either:
    # - user is anonymous (guest) and the ticket exists, or
    # - user is logged in and owns the ticket
    event = ticket.ticketInfo.event if ticket.ticketInfo else None
    qr_data_url = _qr_data_url_for_ticket(ticket)

    return render(
        request,
        "tickets/ticket_details.html",
        {
            "event": event,
            "ticket": ticket,
            "qr_data_url": qr_data_url,
        },
    )


def ticket_list(request):
    """
    Behaviour required by tests:

    - If desired_role == 'attendee' and the user is authenticated:
        * filtername:
            - request.GET['filtername'] if present
            - otherwise str(request.user) (e.g. "u1")
        * tickets:
            - only tickets owned by this user (via attendee profile or email)

    - For all other cases (including guest, organizer, or no desired_role):
        * filtername:
            - request.GET['filtername'] if present
            - otherwise "all"
        * tickets:
            - all tickets in the system

    - ctx['tickets'] is always a QuerySet (never a plain list).
    """

    role = request.session.get("desired_role")

    # For templates: is this user an organizer in "organizer" role?
    is_organizer = False
    if request.user.is_authenticated:
        has_org_profile = OrganizerProfile.objects.filter(user=request.user).exists()
        is_organizer = has_org_profile and role == "organizer"

    # Base queryset for tickets for all branches
    base_qs = Ticket.objects.select_related("ticketInfo__event").order_by("-id")

    if request.user.is_authenticated and role == "attendee":
        # Attendee role: default filtername is the username unless overridden
        filtername = request.GET.get("filtername", str(request.user))

        profile = UserProfile.objects.filter(user=request.user).first()
        filters = Q()

        if profile is not None:
            filters |= Q(attendee=profile)
        if request.user.email:
            filters |= Q(email__iexact=request.user.email)

        tickets = base_qs.filter(filters).distinct()

    else:
        # Any non-attendee role (including guest, organizer, or None):
        # show all tickets, default filtername "all"
        filtername = request.GET.get("filtername", "all")
        tickets = base_qs

    return render(
        request,
        "tickets/ticket_list.html",
        {
            "tickets": tickets,
            "is_organizer": is_organizer,
            "filtername": filtername,
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

    Anonymous users are allowed (tests expect 200/404 without login),
    but if a logged-in user does NOT own the tickets they are redirected.
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
