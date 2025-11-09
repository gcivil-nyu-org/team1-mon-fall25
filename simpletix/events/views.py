from django.shortcuts import render, redirect, get_object_or_404, resolve_url
import os
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.conf import settings
from django.contrib.auth import REDIRECT_FIELD_NAME
from functools import wraps
from urllib.parse import urlencode
from .forms import EventForm
from tickets.models import TicketInfo
from tickets.forms import TicketFormSet
from accounts.models import OrganizerProfile
from django.contrib.auth.decorators import login_required
from .models import Event, Waitlist


# Only import Algolia if not running in CI
if not os.environ.get("CI"):
    from algoliasearch_django import save_record, delete_record
else:
    # Define no-op versions for CI
    def save_record(instance):
        return None

    def delete_record(instance):
        return None


def custom_login_required(
    view_func=None,
    redirect_field_name=REDIRECT_FIELD_NAME,
    login_url=None,
    extra_params=None,
):
    """
    Decorator for views that checks that the user is logged in, redirecting
    to the log-in page if necessary. Adds custom query parameters to the
    redirect URL.

    Args:
        extra_params (dict): A dictionary of parameters to add to the redirect URL.
    """

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if request.user.is_authenticated:
                return view_func(request, *args, **kwargs)

            # --- Construct the redirect URL ---
            path = request.build_absolute_uri()
            resolved_login_url = resolve_url(login_url or settings.LOGIN_URL)

            # Start with the standard 'next' parameter
            login_url_parts = {redirect_field_name: path}

            # Add any extra parameters provided
            if extra_params:
                login_url_parts.update(extra_params)

            # Combine the base login URL with the encoded parameters
            final_login_url = f"{resolved_login_url}?{urlencode(login_url_parts)}"

            return redirect(final_login_url)

        return _wrapped_view

    if view_func:
        return decorator(view_func)
    return decorator


def organizer_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if request.session.get("desired_role") != "organizer":
            raise PermissionDenied("You must be an organizer to perform this action.")
        return view_func(request, *args, **kwargs)

    return _wrapped_view


def organizer_owns_event(view_func):
    """
    Decorator to ensure that:
    - User is logged in
    - User is an organizer
    - User is the organizer who owns the event
    """

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        # Check for organizer profile
        event_id = kwargs.get("event_id")
        if event_id is None:
            raise PermissionDenied("No event ID provided.")

        if request.session.get("desired_role") != "organizer":
            raise PermissionDenied("You must be an organizer to perform this action.")

        event = get_object_or_404(Event, id=event_id)
        if event.organizer.user != request.user:
            raise PermissionDenied("You are not allowed to modify this event.")

        return view_func(request, *args, **kwargs)

    return _wrapped_view


# Create Event
@custom_login_required(extra_params={"role": "organizer"})
@organizer_required
def create_event(request):
    if request.method == "POST":
        form = EventForm(request.POST, request.FILES)
        formset = TicketFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            event = form.save(commit=False)
            event.organizer = OrganizerProfile.objects.get(user=request.user)
            event.save()
            save_record(event)  # Sync with Algolia
            formset.instance = event
            formset.save()
            messages.success(request, "Event created successfully!")
            return redirect("events:event_detail", event_id=event.id)
        else:
            messages.error(request, "Please fix the errors below.")
    else:
        form = EventForm()
        initial_ticket_data = [
            {"category": category} for category, _ in TicketInfo.CATEGORY_CHOICES
        ]
        formset = TicketFormSet(initial=initial_ticket_data)
    return render(
        request,
        "events/create_event.html",
        {
            "form": form,
            "formset": formset,
            "GOOGLE_MAPS_API_KEY": settings.GOOGLE_MAPS_API_KEY,
        },
    )


# Edit Event
@custom_login_required(extra_params={"role": "organizer"})
@organizer_owns_event
def edit_event(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    if request.method == "POST":
        form = EventForm(request.POST, request.FILES, instance=event)
        formset = TicketFormSet(request.POST, request.FILES, instance=event)
        if form.is_valid() and formset.is_valid():
            form.save()
            save_record(event)  # Sync with Algolia
            formset.save()
            messages.success(request, "Event updated successfully!")
            return redirect("events:event_detail", event_id=event.id)
        else:
            messages.error(request, "Please fix the errors below.")
    else:
        form = EventForm(instance=event)
        formset = TicketFormSet(instance=event)
    return render(
        request,
        "events/edit_event.html",
        {
            "form": form,
            "formset": formset,
            "event": event,
            "GOOGLE_MAPS_API_KEY": settings.GOOGLE_MAPS_API_KEY,
        },
    )


# Delete Event
@custom_login_required(extra_params={"role": "organizer"})
@organizer_owns_event
def delete_event(request, event_id):
    event = get_object_or_404(Event, id=event_id)

    if request.method == "POST":
        delete_record(event)  # Remove from Algolia
        event.delete()
        messages.success(request, "Event deleted successfully!")
        return redirect("events:event_list")
    return render(request, "events/delete_event.html", {"event": event})


# Event List
def event_list(request):
    events = Event.objects.all()
    return render(request, "events/event_list.html", {"events": events})


@login_required
def event_detail(request, event_id):
    event = get_object_or_404(Event, pk=event_id)
    tickets_available = event.ticketInfo.filter(availability__gt=0).exists()

    # Handle waitlist join form
    if request.method == "POST":
        if event.waitlist_enabled and not tickets_available:
            existing_entry = Waitlist.objects.filter(
                event=event, user=request.user
            ).first()
            if existing_entry:
                messages.info(
                    request, "You are already on the waitlist for this event."
                )
            else:
                Waitlist.objects.create(event=event, user=request.user)
                messages.success(request, "You've been added to the waitlist!")
            return redirect("events:event_detail", event_id=event.id)
        else:
            messages.error(
                request, "Waitlist is not available or tickets are still available."
            )
            return redirect("events:event_detail", event_id=event.id)

    context = {
        "event": event,
        "tickets_available": tickets_available,
    }
    return render(request, "events/event_detail.html", context)


@login_required
def join_waitlist(request, event_id):
    event = get_object_or_404(Event, id=event_id)

    if not event.waitlist_enabled:
        messages.error(request, "Waitlist is not available for this event.")
        return redirect("events:event_detail", event.id)

    existing = Waitlist.objects.filter(event=event, user=request.user).first()
    if existing:
        messages.info(request, "You are already on the waitlist.")
    else:
        Waitlist.objects.create(event=event, user=request.user)
        messages.success(request, "You’ve been added to the waitlist!")

    return redirect("events:event_detail", event.id)


@login_required
def manage_waitlist(request, event_id):
    event = get_object_or_404(Event, id=event_id)

    # Organizer permission
    if request.user != event.organizer.user:
        messages.error(request, "You do not have permission to manage this waitlist.")
        return redirect("events:event_detail", event.id)

    if request.method == "POST":
        entry_id = request.POST.get("entry_id")
        action = request.POST.get("action")

        try:
            entry = Waitlist.objects.get(id=entry_id, event=event)
            if action == "approve":
                entry.is_approved = True
                entry.save()
                messages.success(
                    request, f"{entry.user.username} approved from waitlist."
                )
            elif action == "reject":
                entry.delete()
                messages.info(request, f"{entry.user.username} removed from waitlist.")
        except Waitlist.DoesNotExist:
            messages.error(request, "Entry not found.")

        return redirect("events:manage_waitlist", event.id)

    waitlist_entries = Waitlist.objects.filter(event=event)
    return render(
        request,
        "events/manage_waitlist.html",
        {"event": event, "waitlist_entries": waitlist_entries},
    )


@login_required
def approve_waitlist(request, entry_id):
    entry = get_object_or_404(Waitlist, id=entry_id)
    event = entry.event

    # Only the event's organizer can approve
    if request.user != event.organizer.user:
        messages.error(
            request, "You are not authorized to approve this waitlist entry."
        )
        return redirect("events:event_detail", event.id)

    # Check if event still has tickets
    tickets_available = event.ticketInfo.filter(availability__gt=0).exists()
    if not tickets_available:
        messages.warning(
            request, "⚠️ Please increase ticket count before approving attendees."
        )

    # Approve anyway
    entry.is_approved = True
    entry.save()
    messages.success(
        request, f"{entry.user.username} has been approved from the waitlist!"
    )

    return redirect("events:manage_waitlist", event.id)
