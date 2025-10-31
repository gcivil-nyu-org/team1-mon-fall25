from django.shortcuts import get_object_or_404, render

from accounts.models import UserProfile
from events.models import Event
from .models import Ticket


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
