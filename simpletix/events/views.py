from django.shortcuts import render

# Create your views here.
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .forms import EventForm, TicketFormSet
from .models import Event

def create_event(request):
    if request.method == 'POST':
        form = EventForm(request.POST, request.FILES)
        formset = TicketFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            event = form.save()
            tickets = formset.save(commit=False)
            for ticket in tickets:
                ticket.event = event
                ticket.save()
            messages.success(request, "Event created successfully!")
            return redirect('event_detail', event.id)
        else:
            messages.error(request, "Please fix the errors below.")
    else:
        form = EventForm()
        formset = TicketFormSet()
    return render(request, 'events/create_event.html', {'form': form, 'formset': formset})

def event_detail(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    return render(request, 'events/event_detail.html', {'event': event})
def event_list(request):
    events = Event.objects.all()
    return render(request, 'events/event_list.html', {'events': events})

