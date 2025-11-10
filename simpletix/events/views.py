from django.shortcuts import render, redirect, get_object_or_404, resolve_url
import os
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.conf import settings
from django.contrib.auth import REDIRECT_FIELD_NAME
from functools import wraps
from urllib.parse import urlencode
from .forms import EventForm
from .models import Event
from tickets.models import TicketInfo
from tickets.forms import TicketFormSet
from accounts.models import OrganizerProfile
from datetime import timedelta, date
from django.db.models import Q
from django.db import models
from django.db.models.functions import Coalesce



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

    # --- Distance (placeholder until geolocation logic added) ---
    distance = request.GET.get("distance")

    # --- Ticket Price Sorting (General Admission only) ---
    price_sort = request.GET.get("price_sort")
    if price_sort:
        # Join TicketInfo to allow sorting by GA price, but don't exclude others
        events = events.annotate(
            general_price=Coalesce(
                models.Subquery(
                    TicketInfo.objects.filter(
                        event=models.OuterRef("pk"),
                        category="General Admission"
                    ).values("price")[:1]
                ),
                999999,  # default price if no GA ticket
                output_field=models.DecimalField(max_digits=8, decimal_places=2)
            )
        )


        if price_sort == "asc":
            events = events.order_by("general_price", "date")
        elif price_sort == "desc":
            events = events.order_by("-general_price", "date")



    # --- State Filter ---
    state = request.GET.get("state")
    if state:
        events = events.filter(
            Q(formatted_address__icontains=state.split()[0]) | Q(location__icontains=state)
        )


    # --- Ticket Type Filter (must have all selected ticket types available) ---
    selected_ticket_types = request.GET.getlist("ticket_type")
    if selected_ticket_types:
        for t_type in selected_ticket_types:
            if t_type == "general":
                events = events.filter(
                    ticketInfo__category="General Admission",
                    ticketInfo__availability__gt=0
                )
            elif t_type == "earlybird":
                events = events.filter(
                    ticketInfo__category="Early Bird",
                    ticketInfo__availability__gt=0
                )
            elif t_type == "vip":
                events = events.filter(
                    ticketInfo__category="VIP",
                    ticketInfo__availability__gt=0
                )
        events = events.distinct()



    # --- Date Range Filter (user-selected start/end) ---
    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")

    if start_date and end_date:
        events = events.filter(date__range=[start_date, end_date])
    elif start_date:
        events = events.filter(date__gte=start_date)
    elif end_date:
        events = events.filter(date__lte=end_date)


    # --- Available States (for dropdown) ---
    all_states = []
    for ev in Event.objects.exclude(formatted_address="").values_list("formatted_address", flat=True):
        parts = ev.split(",")
        if len(parts) >= 2:
            state_part = parts[-2].strip()
            # normalize: remove ZIP codes (e.g., "NY 10001" -> "NY")
            state_part = state_part.split()[0]
            all_states.append(state_part)

    available_states = sorted(list(set(all_states)))

    context = {
        "events": events.distinct(),
        "available_states": available_states,
        "selected_ticket_types": selected_ticket_types,
    } 

    return render(request, "events/event_list.html", context)

# Event Detail
def event_detail(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    return render(request, "events/event_detail.html", {"event": event})
