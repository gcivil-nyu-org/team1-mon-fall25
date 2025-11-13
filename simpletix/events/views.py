from functools import wraps
from urllib.parse import urlencode
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.core.exceptions import PermissionDenied
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
    resolve_url,
)

from accounts.models import OrganizerProfile
from tickets.forms import TicketFormSet
from .forms import EventForm
from .models import Event, EventTimeSlot

# --- Algolia integration helpers -------------------------------------------

try:
    from algoliasearch_django import (
        save_record as _save_record,
        delete_record as _delete_record,
    )
except Exception:
    # If Algolia isn't installed or is misconfigured, fail gracefully.
    _save_record = None
    _delete_record = None


def algolia_save(instance):
    """
    Save an instance to Algolia if Algolia is enabled.
    In dev/prod this will run normally.
    In tests/CI you can disable it via settings.ALGOLIA_ENABLED = False.
    """
    if not getattr(settings, "ALGOLIA_ENABLED", True):
        return
    if _save_record is not None:
        _save_record(instance)


def algolia_delete(instance):
    """
    Delete an instance from Algolia if Algolia is enabled.
    """
    if not getattr(settings, "ALGOLIA_ENABLED", True):
        return
    if _delete_record is not None:
        _delete_record(instance)


# --- Auth / role decorators -------------------------------------------------


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


# --- Views ------------------------------------------------------------------


@custom_login_required(extra_params={"role": "organizer"})
@organizer_required
def create_event(request):
    if request.method == "POST":
        form = EventForm(request.POST, request.FILES)
        formset = TicketFormSet(request.POST)

        if form.is_valid() and formset.is_valid():
            # Save event linked to organizer
            event = form.save(commit=False)
            event.organizer = OrganizerProfile.objects.get(user=request.user)
            event.save()

            # Save tickets
            tickets = formset.save(commit=False)
            for ticket in tickets:
                ticket.event = event
                ticket.save()

            # Save time slots
            slot_dates = request.POST.getlist("slot_date[]")
            slot_start_times = request.POST.getlist("slot_start_time[]")
            slot_end_times = request.POST.getlist("slot_end_time[]")

            for date, start_time, end_time in zip(
                slot_dates, slot_start_times, slot_end_times
            ):
                EventTimeSlot.objects.create(
                    event=event, date=date, start_time=start_time, end_time=end_time
                )

            messages.success(request, "Event created successfully!")
            return redirect("events:event_list")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = EventForm()
        # Prepopulate ticket categories
        initial_tickets = [
            {"category": "General Admission", "price": 0, "availability": 0},
            {"category": "VIP", "price": 0, "availability": 0},
            {"category": "Early Bird", "price": 0, "availability": 0},
        ]
        formset = TicketFormSet(initial=initial_tickets)

    context = {
        "form": form,
        "formset": formset,
        "GOOGLE_MAPS_API_KEY": settings.GOOGLE_MAPS_API_KEY,
    }
    return render(request, "events/create_event.html", context)


@custom_login_required(extra_params={"role": "organizer"})
@organizer_owns_event
def edit_event(request, event_id):
    event = get_object_or_404(Event, id=event_id)

    if request.method == "POST":
        form = EventForm(request.POST, request.FILES, instance=event)
        formset = TicketFormSet(request.POST, instance=event)

        if form.is_valid() and formset.is_valid():
            event = form.save()
            formset.save()

            # Delete existing time slots and recreate
            event.time_slots.all().delete()

            slot_dates = request.POST.getlist("slot_date[]")
            slot_start_times = request.POST.getlist("slot_start_time[]")
            slot_end_times = request.POST.getlist("slot_end_time[]")

            for date, start_time, end_time in zip(
                slot_dates, slot_start_times, slot_end_times
            ):
                EventTimeSlot.objects.create(
                    event=event, date=date, start_time=start_time, end_time=end_time
                )

            algolia_save(event)
            messages.success(request, "Event updated successfully!")
            return redirect("events:event_list")
        else:
            messages.error(request, "Please correct the errors.")
    else:
        form = EventForm(instance=event)
        formset = TicketFormSet(instance=event)
        existing_slots = event.time_slots.all()

    return render(
        request,
        "events/edit_event.html",
        {
            "form": form,
            "formset": formset,
            "event": event,
            "existing_slots": existing_slots,
            "GOOGLE_MAPS_API_KEY": settings.GOOGLE_MAPS_API_KEY,
        },
    )


@custom_login_required(extra_params={"role": "organizer"})
@organizer_owns_event
def delete_event(request, event_id):
    event = get_object_or_404(Event, id=event_id)

    if request.method == "POST":
        algolia_delete(event)
        event.delete()
        messages.success(request, "Event deleted successfully!")
        return redirect("events:event_list")

    return render(request, "events/delete_event.html", {"event": event})


def event_list(request):
    events = (
        Event.objects.all().prefetch_related("ticketInfo", "time_slots").order_by("-id")
    )
    return render(request, "events/event_list.html", {"events": events})


def event_detail(request, event_id):
    event = get_object_or_404(Event.objects.prefetch_related("time_slots"), id=event_id)
    return render(request, "events/event_detail.html", {"event": event})
