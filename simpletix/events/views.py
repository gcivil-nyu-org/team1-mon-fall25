from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .forms import EventForm
from .models import Event
from tickets.models import TicketInfo
from tickets.forms import TicketFormSet
from accounts.models import OrganizerProfile
from algoliasearch_django import save_record, delete_record



# Create Event
def create_event(request):
    if request.method == 'POST':
        form = EventForm(request.POST, request.FILES)
        formset = TicketFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            event = form.save(commit=False)
            event.organizer = OrganizerProfile.objects.get(user=request.user)
            event.save()
            save_record(event) # Add the event to Algolia
            formset.instance = event
            formset.save()
            messages.success(request, "Event created successfully!")
            return redirect('events:event_detail', event_id=event.id)
        else:
            messages.error(request, "Please fix the errors below.")
    else:
        form = EventForm()
        initial_ticket_data = [
            {'category': category} for category, _ in TicketInfo.CATEGORY_CHOICES
        ]
        formset = TicketFormSet(initial=initial_ticket_data)
    return render(request, 'events/create_event.html', {'form': form, 'formset': formset})


# Edit Event
def edit_event(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    if request.method == 'POST':
        form = EventForm(request.POST, request.FILES, instance=event)
        formset = TicketFormSet(request.POST, request.FILES, instance=event)
        if form.is_valid() and formset.is_valid():
            form.save()
            # ✅ Correct
            save_record(event) # Update the event in Algolia
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
        delete_record(event) # Remove the event from Algolia
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
