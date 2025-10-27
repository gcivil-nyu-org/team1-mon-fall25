from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import UserProfile
from events.models import Event
from .forms import OrderForm
from .models import Ticket


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
