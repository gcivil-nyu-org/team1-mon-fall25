from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import UserProfile
from events.models import Event
from .forms import OrderForm
from .models import Ticket
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from . import services
from .models import TicketInfo


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
    Temporary endpoint to be called by payment flow.
    Expects: order_id, ticket_info_id, full_name, email, phone
    Once orders app is merged, we will switch to FK.
    """
    data = json.loads(request.body)
    order_id = data.get("order_id")
    ticket_info_id = data.get("ticket_info_id")

    if not order_id or not ticket_info_id:
        return JsonResponse({"error": "order_id and ticket_info_id required"}, status=400)

    ti = TicketInfo.objects.get(id=ticket_info_id)

    ticket = services.issue_ticket_for_order_id(
        order_id=order_id,
        ticket_info=ti,
        full_name=data.get("full_name", ""),
        email=data.get("email", ""),
        phone=data.get("phone", ""),
    )

    # TODO: later attach PDF + send email
    return JsonResponse({"status": "ok", "ticket_id": ticket.id})