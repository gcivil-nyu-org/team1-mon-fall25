from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from .models import Event
from accounts.models import OrganizerProfile
from .forms import EventForm
from tickets.models import TicketInfo
from tickets.forms import TicketFormSet

# ---------------------------
# Decorators
# ---------------------------
def organizer_required(view_func):
    def _wrapped_view(request, *args, **kwargs):
        if request.session.get("desired_role") != "organizer":
            raise PermissionDenied("You must be an organizer to perform this action.")
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def organizer_owns_event(view_func):
    def _wrapped_view(request, *args, **kwargs):
        event_id = kwargs.get("event_id")
        if event_id is None:
            raise PermissionDenied("No event ID provided.")
        event = get_object_or_404(Event, id=event_id)
        if event.organizer.user != request.user:
            raise PermissionDenied("You are not allowed to modify this event.")
        return view_func(request, *args, **kwargs)
    return _wrapped_view

# ---------------------------
# Event Views
# ---------------------------

def event_list(request):
    events = Event.objects.all().prefetch_related("ticketInfo")
    return render(request, "events/event_list.html", {"events": events})


def event_detail(request, event_id):
    event = get_object_or_404(Event.objects.prefetch_related("ticketInfo"), id=event_id)
    return render(request, "events/event_detail.html", {"event": event})


@organizer_required
def create_event(request):
    if request.method == "POST":
        form = EventForm(request.POST, request.FILES)
        formset = TicketFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            event = form.save(commit=False)
            event.organizer = OrganizerProfile.objects.get(user=request.user)
            event.save()
            formset.instance = event
            formset.save()
            messages.success(request, "Event created successfully!")
            return redirect("events:event_detail", event_id=event.id)
        else:
            messages.error(request, "Please fix the errors below.")
    else:
        form = EventForm()
        initial_ticket_data = [{"category": category} for category, _ in TicketInfo.CATEGORY_CHOICES]
        formset = TicketFormSet(initial=initial_ticket_data)
    return render(request, "events/create_event.html", {"form": form, "formset": formset})


@organizer_required
@organizer_owns_event
def edit_event(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    if request.method == "POST":
        form = EventForm(request.POST, request.FILES, instance=event)
        formset = TicketFormSet(request.POST, request.FILES, instance=event)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, "Event updated successfully!")
            return redirect("events:event_detail", event_id=event.id)
        else:
            messages.error(request, "Please fix the errors below.")
    else:
        form = EventForm(instance=event)
        formset = TicketFormSet(instance=event)
    return render(request, "events/edit_event.html", {"form": form, "formset": formset, "event": event})


@organizer_required
@organizer_owns_event
def delete_event(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    if request.method == "POST":
        event.delete()
        messages.success(request, "Event deleted successfully!")
        return redirect("events:event_list")
    return render(request, "events/delete_event.html", {"event": event})
