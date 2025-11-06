from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import UserProfile
from events.models import Event
from .forms import OrderForm
from .models import Ticket
import json
from django.views.decorators.csrf import csrf_exempt
from . import services
from .models import TicketInfo
from django.http import JsonResponse, HttpResponseNotAllowed


def index(request):
    return render(request, "tickets/index.html")


def order(request, id):
    event = get_object_or_404(Event, id=id)

    if request.method == "POST":
        # Pass the event object to the form constructor
        form = OrderForm(request.POST, event=event)

        if form.is_valid():
            try:
                # Use a database transaction to ensure data integrity
                with transaction.atomic():
                    # Save the form to create the ticket instance
                    ticket = form.save(commit=False)
                    if request.session.get("desired_role") == "attendee":
                        ticket.attendee = UserProfile.objects.get(user=request.user)
                    ticket.save()

                    # Decrement the availability of the chosen TicketInfo
                    ticket_info = form.cleaned_data["ticketInfo"]
                    ticket_info.availability -= 1
                    ticket_info.save()

                return redirect("tickets:ticket_details", id=ticket.id)
            except Exception as e:  # pragma: no cover (optional)
                # You may want to log this instead of print in production
                print(e)
    else:
        # For a GET request, pass the event object to the form
        form = OrderForm(event=event)

    return render(
        request,
        "tickets/order.html",
        {"event": event, "form": form},
    )


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
            "message": "Ticket issued and email sent.",
        },
        status=200,
    )
