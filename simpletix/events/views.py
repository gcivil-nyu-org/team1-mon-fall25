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
from tickets.models import TicketInfo
from orders.models import Order
from .forms import EventForm
from .models import Event

from django.db import models, transaction
from django.db.models.functions import Coalesce
from django.db.models import F
from django.db.models.functions import ACos, Cos, Sin, Radians
from django.db.utils import IntegrityError
from django.contrib.auth.decorators import login_required

from . import services

from django.views.decorators.http import require_POST
from django.db import IntegrityError
from events.models import Event, EventNotificationSubscription 
from django.core.mail import send_mail 


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


# Create Event
@custom_login_required(extra_params={"role": "organizer"})
@organizer_required
def create_event(request):
    initial_ticket_data = [
        {"category": category} for category, _ in TicketInfo.CATEGORY_CHOICES
    ]
    if request.method == "POST":
        form = EventForm(request.POST, request.FILES)
        formset = TicketFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            event = form.save(commit=False)
            event.organizer = OrganizerProfile.objects.get(user=request.user)
            event.save()

            algolia_save(event)

            formset.instance = event
            formset.save()
            messages.success(request, "Event created successfully!")
            return redirect("events:event_detail", event_id=event.id)
        else:
            messages.error(request, "Please fix the errors below.")
            for i, ticket_form in enumerate(formset.forms):
                if i < len(initial_ticket_data):
                    ticket_form.initial.update(initial_ticket_data[i])
    else:
        form = EventForm()
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

        # Category is fixed per ticket on the edit page; don't require it
        for f in formset.forms:
            field = f.fields.get("category")
            if field is not None:
                field.required = False

        if form.is_valid() and formset.is_valid():
            try:
                # Save event + tickets in one transaction
                with transaction.atomic():
                    form.save()
                    algolia_save(event)
                    formset.save()
            except IntegrityError:
                # Most likely: duplicate (event, category) for TicketInfo
                messages.error(
                    request,
                    (
                        "There is already a ticket with that category for this event. "
                        "Each ticket category must be unique per event. "
                        "Please adjust your ticket rows and try again."
                    ),
                )
                # fall through to re-render the form with current data
            else:
                messages.success(request, "Event updated successfully!")
                return redirect("events:event_detail", event_id=event.id)
        # No explicit messages.error here — we show inline errors in the template
    else:
        form = EventForm(instance=event)
        formset = TicketFormSet(instance=event)

        # Relax category requirement on initial render too
        for f in formset.forms:
            field = f.fields.get("category")
            if field is not None:
                field.required = False

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
        has_orders = Order.objects.filter(ticket_info__event=event).exists()
        if has_orders:
            # If orders exist, stop and send a friendly error
            messages.error(
                request, "This event cannot be deleted because it has existing orders."
            )
            # Redirect back to the event detail page (or wherever is appropriate)
            return redirect("events:event_detail", event_id=event.id)

        algolia_delete(event)

        event.delete()
        messages.success(request, "Event deleted successfully!")
        return redirect("events:event_list")
    return render(request, "events/delete_event.html", {"event": event})


# Event List
# --- Event List (stable + slick-compatible version) ---
def event_list(request):
    events = Event.objects.all().distinct()

    # --- Sorting Inputs ---
    price_sort = request.GET.get("price_sort")
    date_sort = request.GET.get("date_sort")
    distance_sort = request.GET.get("distance_sort")

    user_lat = request.GET.get("user_lat")
    user_lng = request.GET.get("user_lng")

    # Annotate price if used in sorting
    if price_sort:
        events = events.annotate(
            general_price=Coalesce(
                models.Subquery(
                    TicketInfo.objects.filter(
                        event=models.OuterRef("pk"), category="General Admission"
                    ).values("price")[:1]
                ),
                999999,
                output_field=models.DecimalField(max_digits=8, decimal_places=2),
            )
        )

    # Annotate distance only if near/far + coords present
    if distance_sort in ["near", "far"] or request.GET.get("radius"):
        try:
            user_lat = float(user_lat)
            user_lng = float(user_lng)
        except (TypeError, ValueError):
            user_lat = user_lng = None

        if user_lat and user_lng:
            events = events.annotate(
                distance_km=6371
                * ACos(
                    Cos(Radians(user_lat))
                    * Cos(Radians(F("latitude")))
                    * Cos(Radians(F("longitude")) - Radians(user_lng))
                    + Sin(Radians(user_lat)) * Sin(Radians(F("latitude")))
                )
            )
    else:
        # No valid coordinates → disable distance-based ordering/filtering
        distance_sort = None

    # --- Hybrid Sorting Logic ---
    ordering = []

    # 1. Date sorting (highest priority when chosen)
    if date_sort == "soon":
        ordering += ["date", "time"]
    elif date_sort == "late":
        ordering += ["-date", "-time"]

    # 2. Price sorting
    if price_sort == "asc":
        ordering.append("general_price")
    elif price_sort == "desc":
        ordering.append("-general_price")

    # 3. Distance sorting (lowest priority)
    if distance_sort == "near":
        ordering.append("distance_km")
    elif distance_sort == "far":
        ordering.append("-distance_km")

    # Remove distance ordering if no distance_km annotation exists
    if ("distance_km" in ordering or "-distance_km" in ordering) and (
        "distance_km" not in events.query.annotations
    ):
        ordering = [o for o in ordering if o not in ("distance_km", "-distance_km")]

    # Apply ordering
    if ordering:
        events = events.order_by(*ordering)

    # --- Radius Filter ---
    radius = request.GET.get("radius")
    if radius and user_lat and user_lng:
        try:
            radius_miles = float(radius)
            radius_km = radius_miles * 1.60934  # convert to km
            events = events.filter(distance_km__lte=radius_km)
        except ValueError:
            pass

    """
    # --- Multi-State Filter ---
    selected_states = request.GET.getlist("state")
    if selected_states:
        state_filter = Q()
        for st in selected_states:
            state_filter |= Q(formatted_address__icontains=st) | Q(
                location__icontains=st
            )
        events = events.filter(state_filter)
    """

    # --- Ticket Type Filter (multi-select) ---
    selected_ticket_types = request.GET.getlist("ticket_type")
    if selected_ticket_types:
        type_map = {
            "general": "General Admission",
            "earlybird": "Early Bird",
            "vip": "VIP",
        }
        for t_type in selected_ticket_types:
            events = events.filter(
                ticketInfo__category=type_map.get(t_type, t_type),
                ticketInfo__availability__gt=0,
            )

    # --- Date Range Filter ---
    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")
    if start_date and end_date:
        events = events.filter(date__range=[start_date, end_date])
    elif start_date:
        events = events.filter(date__gte=start_date)
    elif end_date:
        events = events.filter(date__lte=end_date)

    """
    # --- Available States for Dropdown ---
    all_states = []
    for addr in Event.objects.exclude(formatted_address="").values_list(
        "formatted_address", flat=True
    ):
        parts = addr.split(",")
        if len(parts) >= 2:
            state_part = parts[-2].strip().split()[0]
            all_states.append(state_part)
    available_states = sorted(set(all_states))
    """

    # --- Context ---
    context = {
        "events": events.distinct(),
        # "available_states": available_states,
        "selected_ticket_types": selected_ticket_types,
        # "selected_states": selected_states,
        "selected_price_sort": price_sort,
        "selected_date_sort": date_sort,
        "start_date": start_date,
        "end_date": end_date,
    }

    return render(request, "events/event_list.html", context)

# Event Detail
def event_detail(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    
    # NEW: Check if event is sold out
    from tickets.models import TicketInfo
    
    active_tickets = TicketInfo.objects.filter(event=event, is_active=True)
    available_tickets = active_tickets.filter(availability__gt=0)
    
    is_sold_out = active_tickets.exists() and not available_tickets.exists()
    
    # NEW: Count subscribers
    subscriber_count = EventNotificationSubscription.objects.filter(
        event=event
    ).count()
    
    return render(request, "events/event_detail.html", {
        "event": event,
        "is_sold_out": is_sold_out,
        "subscriber_count": subscriber_count,

    })
# NEW: Subscribe to notifications
@require_POST
def subscribe_notification(request, event_id):
    """
    Subscribe user to notifications when tickets become available.
    Email sending will be implemented later.
    """
    event = get_object_or_404(Event, id=event_id)
    
    email = request.POST.get('email', '').strip()
    name = request.POST.get('name', '').strip()
    
    # If user is logged in, use their info
    if request.user.is_authenticated:
        if not email:
            email = request.user.email
        if not name:
            name = request.user.get_full_name() or request.user.username
    
    # Validate email
    if not email:
        messages.error(request, "Email address is required.")
        return redirect('events:event_detail', event_id=event_id)
    
    try:
        # Create subscription
        subscription, created = EventNotificationSubscription.objects.get_or_create(
            event=event,
            email=email,
            defaults={'name': name}
        )
        
        if created:
            messages.success(
                request, 
                f"✅ You're on the list! We'll notify {email} when tickets are available."
            )
        else:
            messages.info(
                request, 
                "You're already subscribed to notifications for this event."
            )
    
    except IntegrityError:
        messages.error(request, "Error subscribing. Please try again.")
    
    return redirect('events:event_detail', event_id=event_id)


# NEW: View subscriber list (organizer only)
def notification_subscribers(request, event_id):
    """
    Show list of people waiting for ticket notifications.
    Only accessible to event organizer.
    """
    event = get_object_or_404(Event, id=event_id)
    
    # Check if user is organizer
    if request.session.get('desired_role') != 'organizer':
        messages.error(request, "Only organizers can view subscribers.")
        return redirect('events:event_detail', event_id=event_id)
    
    if event.organizer.user != request.user:
        messages.error(request, "You can only view subscribers for your own events.")
        return redirect('events:event_detail', event_id=event_id)
    
    # Get all subscribers
    subscribers = EventNotificationSubscription.objects.filter(
        event=event
    ).order_by('-created_at')
    
    return render(request, 'events/notification_subscribers.html', {
        'event': event,
        'subscribers': subscribers,
    })
    


@require_POST
def subscribe_notification(request, event_id):
    """
    Subscribe user to notifications when tickets become available.
    Sends a confirmation email when subscription is first created.
    """
    event = get_object_or_404(Event, id=event_id)

    email = request.POST.get("email", "").strip()
    name = request.POST.get("name", "").strip()

    # If user is logged in, use their info as fallback
    if request.user.is_authenticated:
        if not email:
            email = request.user.email
        if not name:
            name = request.user.get_full_name() or request.user.username

    # Validate email
    if not email:
        messages.error(request, "Email address is required.")
        return redirect("events:event_detail", event_id=event_id)

    try:
        subscription, created = EventNotificationSubscription.objects.get_or_create(
            event=event,
            email=email,
            defaults={"name": name},
        )

        if created:
            # Flash message
            messages.success(
                request,
                f" You're on the list! We'll notify {email} when tickets are available.",
            )

            # --- NEW: confirmation email ---
            subject = f"You're on the waitlist for {event.title}"
            greeting_name = (
                subscription.name
                or (request.user.get_full_name() if request.user.is_authenticated else "")
                or "there"
            )

            message = (
                f"Hi {greeting_name},\n\n"
                f"Thanks for your interest in '{event.title}'. "
                "Tickets are currently sold out, but we've added you to the waitlist.\n\n"
                "We'll email you at this address as soon as more tickets become "
                "available for this event.\n\n"
                "Best,\n"
                "SimpleTix Team"
            )

            from_email = getattr(
                settings, "DEFAULT_FROM_EMAIL", "no-reply@example.com"
            )

            send_mail(
                subject,
                message,
                from_email,
                [email],
                fail_silently=True,  
            )

        else:
            messages.info(
                request,
                "You're already subscribed to notifications for this event.",
            )

    except IntegrityError:
        messages.error(request, "Error subscribing. Please try again.")

    return redirect("events:event_detail", event_id=event_id)
    
    return render(request, "events/event_detail.html", {"event": event})


def _get_organizer_profile(user):
    """
    Best-effort helper to get OrganizerProfile from user.
    Handles both `user.organizerprofile` and `user.organizer_profile`.
    """
    if not user.is_authenticated:
        return None
    return getattr(user, "organizerprofile", None) or getattr(
        user, "organizer_profile", None
    )


@login_required
def event_management_dashboard(request):
    organizer_profile = _get_organizer_profile(request.user)

    if organizer_profile is None:
        messages.error(request, "You must be an organizer to access this page.")
        return redirect("events:event_list")  # fallback

    events = Event.objects.filter(organizer=organizer_profile).order_by(
        "-date", "-time"
    )

    return render(
        request,
        "events/event_management_dashboard.html",
        {"events": events},
    )


@login_required
def cancel_event(request, event_id):
    organizer_profile = _get_organizer_profile(request.user)

    if organizer_profile is None:
        messages.error(request, "You must be an organizer to cancel an event.")
        return redirect("home")

    event = get_object_or_404(Event, id=event_id)

    if event.organizer != organizer_profile and not request.user.is_staff:
        messages.error(request, "You are not allowed to cancel this event.")
        return redirect("events:event_management_dashboard")

    if event.is_cancelled:
        messages.info(request, "This event is already cancelled.")
        return redirect("events:event_management_dashboard")

    if request.method == "POST":
        # 1) Update event status
        event.cancel()

        # 2) Notify all attendees with completed orders
        services.notify_event_cancellation(event)

        # 3) Trigger refund pipeline @Xiangping
        services.initiate_event_refunds(event)

        messages.success(
            request,
            f'"{event.title}" has been cancelled. '
            "Attendees will be notified and refunds will be processed.",
        )
        return redirect("events:event_management_dashboard")

    return render(request, "events/confirm_cancel_event.html", {"event": event})
