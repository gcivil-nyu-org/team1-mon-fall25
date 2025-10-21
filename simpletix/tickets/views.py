from django.shortcuts import get_object_or_404, render, redirect
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse
from django.db.models import F
from django.contrib import messages
from django.db import transaction

from events.models import Event
from .forms import OrderForm
from .models import Ticket
from accounts.models import UserProfile


# Create your views here.

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
                    if request.session.get('desired_role') == 'attendee':
                        ticket.attendee = UserProfile.objects.get(user=request.user)
                    ticket.save()
                    
                    # Decrement the availability of the chosen TicketInfo
                    ticket_info = form.cleaned_data['ticketInfo']
                    ticket_info.availability -= 1
                    ticket_info.save()

                # messages.success(request, "Your ticket has been successfully booked!")
                return redirect('tickets:ticket_details', id=ticket.id)
            except Exception as e:
                # messages.error(request, "An unexpected error occurred. Please try again.")
                print(e) # For debugging
    else:
        # For a GET request, pass the event object to the form
        form = OrderForm(event=event)
        
    return render(request, "tickets/order.html", {'event': event, 'form': form})


def details(request, id):
    ticket = get_object_or_404(Ticket, id=id)
    event = get_object_or_404(Event, id=ticket.ticketInfo.event.id)
    return render(request, "tickets/ticket_details.html", { 'event': event, 'ticket': ticket })

def ticket_list(request):
    if request.session.get('desired_role') == 'attendee':
        attendee= UserProfile.objects.get(user=request.user)
        filtername = attendee.user
        tickets = Ticket.objects.filter(attendee = attendee)
    else:
        filtername = 'all'
        tickets = Ticket.objects.all()
    return render(request, "tickets/ticket_list.html", { 'filtername': filtername, 'tickets': tickets})