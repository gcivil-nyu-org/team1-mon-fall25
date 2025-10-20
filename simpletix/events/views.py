from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .forms import EventForm, TicketFormSet
from .models import Event

# Create Event
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
            return redirect('events:event_detail', event_id=event.id)
        else:
            messages.error(request, "Please fix the errors below.")
    else:
        form = EventForm()
        formset = TicketFormSet()
    return render(request, 'events/create_event.html', {'form': form, 'formset': formset})

# Edit Event
def edit_event(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    if request.method == 'POST':
        form = EventForm(request.POST, request.FILES, instance=event)
        formset = TicketFormSet(request.POST, request.FILES, instance=event)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, "Event updated successfully!")
            return redirect('events:event_detail', event_id=event.id)
        else:
            messages.error(request, "Please fix the errors below.")
    else:
        form = EventForm(instance=event)
        formset = TicketFormSet(instance=event)
    return render(request, 'events/edit_event.html', {'form': form, 'formset': formset, 'event': event})

# Delete Event
def delete_event(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    if request.method == 'POST':
        event.delete()
        messages.success(request, "Event deleted successfully!")
        return redirect('events:event_list')
    return render(request, 'events/delete_event.html', {'event': event})

# Event List
def event_list(request):
    events = Event.objects.all()
    return render(request, 'events/event_list.html', {'events': events})

# Event Detail
def event_detail(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    return render(request, 'events/event_detail.html', {'event': event})
