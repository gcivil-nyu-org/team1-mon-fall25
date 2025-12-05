from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from decimal import Decimal

from accounts.models import UserProfile
from events.models import Event
from events.views import custom_login_required, organizer_owns_event
from tickets.models import TicketInfo
from tickets import services as ticket_services
from .services import send_refund_email
from .forms import OrderForm
from .models import BillingInfo, Order
import os
import time
import stripe


def order(request, event_id):
    """
    Create an order for a given event.

    Behaviour required by tests:
    - GET:
      * Renders orders/order.html with an OrderForm(event=event, profile=profile).
      * If ?ticket_category_id=<valid available id> is provided:
          - form.initial["ticket_info"] == that ticket's ID
          - quantity max / max_value == that ticket's availability
      * If ticket_category_id is invalid or sold-out:
          - no initial["ticket_info"]
          - quantity max / max_value == first available ticket's availability
    - POST:
      * Creates an Order, decrements availability, redirects to process_payment.
      * Links order.attendee if desired_role == "attendee".
    - Organizer role (desired_role == "organizer") is blocked from buying.
    """
    event = get_object_or_404(Event, id=event_id)
    if event.is_cancelled:
        messages.error(
            request,
            "This event has been cancelled. Ticket purchases are no longer available.",
        )
        return redirect("events:event_detail", event_id=event.id)

    desired_role = request.session.get("desired_role")

    # Block organizers from purchasing
    if request.user.is_authenticated and desired_role == "organizer":
        messages.error(
            request,
            (
                "Organizer accounts cannot purchase tickets. "
                "Please log in with an attendee account to buy tickets."
            ),
        )
        return redirect("events:event_detail", event_id=event.id)

    # Build profile (if any) so the form can pre-populate email
    profile = None
    if request.user.is_authenticated:
        profile = UserProfile.objects.filter(user=request.user).first()

    if request.method == "POST":
        form = OrderForm(request.POST, event=event, profile=profile)

        if form.is_valid():
            with transaction.atomic():
                ticket_info = form.cleaned_data.get("ticket_info")
                quantity = form.cleaned_data.get("quantity", 1)

                if ticket_info is None:
                    available_tickets = TicketInfo.objects.filter(
                        event=event, availability__gt=0, is_active=True
                    )
                    ticket_availability_data = {
                        str(t.id): t.availability for t in available_tickets
                    }
                    return render(
                        request,
                        "orders/order.html",
                        {
                            "event": event,
                            "form": form,
                            "ticket_availability_data": ticket_availability_data,
                        },
                    )

                # Lock this TicketInfo row
                ticket_info = TicketInfo.objects.select_for_update().get(
                    pk=ticket_info.pk
                )

                if quantity < 1:
                    messages.error(request, "Please select at least one ticket.")
                    return redirect("orders:order", event_id=event.id)

                if ticket_info.availability < 1:
                    messages.error(
                        request,
                        "Sorry, this ticket is now sold out.",
                    )
                    return redirect("orders:order", event_id=event.id)

                # Decrement availability by requested quantity
                ticket_info.availability -= quantity
                ticket_info.save()

                # Create the Order instance
                order_obj = form.save(commit=False)

                if desired_role == "attendee" and request.user.is_authenticated:
                    attendee_profile = profile
                    if attendee_profile:
                        order_obj.attendee = attendee_profile

                order_obj.save()

            # Successful POST → go to payment step
            return redirect("orders:process_payment", order_id=order_obj.id)

    else:
        # GET: preselect via ?ticket_category_id= and adjust quantity max
        available_tickets = TicketInfo.objects.filter(
            event=event, availability__gt=0, is_active=True
        )

        initial = {}
        selected_ticket = None

        ticket_category_id = request.GET.get("ticket_category_id")
        if ticket_category_id:
            try:
                tid = int(ticket_category_id)
                selected_ticket = available_tickets.get(pk=tid)
                initial["ticket_info"] = selected_ticket.id
            except (ValueError, TicketInfo.DoesNotExist):
                selected_ticket = None  # fall back to first ticket

        form = OrderForm(event=event, profile=profile, initial=initial)

        if available_tickets.exists():
            if selected_ticket is not None:
                max_avail = selected_ticket.availability
            else:
                first_ticket = available_tickets.first()
                max_avail = first_ticket.availability

            form.fields["quantity"].widget.attrs["max"] = max_avail
            form.fields["quantity"].max_value = max_avail

    available_tickets = TicketInfo.objects.filter(
        event=event, availability__gt=0, is_active=True
    )
    ticket_availability_data = {str(t.id): t.availability for t in available_tickets}

    return render(
        request,
        "orders/order.html",
        {
            "event": event,
            "form": form,
            "ticket_availability_data": ticket_availability_data,
        },
    )


def order_failed(order):
    """
    Mark an order as failed and restock the ticket inventory.
    Safe to call multiple times; only affects 'pending' orders.
    """
    if order.status == "pending":
        order.status = "failed"
        order.save()

        ticket_info = order.ticket_info
        ticket_info.availability += order.quantity
        ticket_info.save()


# test card:
# https://docs.stripe.com/testing
# test link info:
# https://docs.stripe.com/connect/testing-verification?connect-account-creation-pattern=typed
def process_payment(request, order_id):
    """
    This view is called when the user clicks "Buy Ticket".
    It redirects the user to Stripe to pay for an existing 'pending' Order.
    """

    order = get_object_or_404(Order, id=order_id)

    if order.status != "pending":
        return redirect("orders:payment_cancel", order_id=order_id)

    ticket_info = order.ticket_info

    stripe.api_key = settings.STRIPE.get("STRIPE_SECRET_KEY", "")

    scheme = request.scheme
    host = request.get_host()
    DOMAIN = f"{scheme}://{host}"

    try:
        product_name = f"{ticket_info.event.title} - {ticket_info.category}"
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "product_data": {
                            "name": product_name,
                        },
                        # Price must be in cents
                        "unit_amount": int(ticket_info.price * 100),
                    },
                    "quantity": order.quantity,
                }
            ],
            mode="payment",
            customer_creation="always",  # Creates a Stripe Customer object
            phone_number_collection={
                "enabled": True,
            },
            # IMPORTANT: Pass the Order ID in metadata
            # This is how our webhook will find the order later
            metadata={
                "order_id": order.id,
                "environment": os.getenv("ENVIRONMENT", "development"),
            },
            expires_at=int(time.time()) + 1800,
            # Redirect URLs
            success_url=DOMAIN + reverse("orders:payment_success", args=[order.id]),
            cancel_url=DOMAIN + reverse("orders:payment_cancel", args=[order.id]),
        )

        order.stripe_session_id = session.id
        order.save()

        # for test
        print("session id:", session.id)

        # Redirect the user to Stripe's payment page
        return redirect(session.url, code=303)

    except Exception as e:
        print(f"Stripe Error: {e}")

        try:
            with transaction.atomic():
                order = Order.objects.get(id=order_id)
                order_failed(order)
        except Exception as inner_e:  # pragma: no cover
            order_info = f"{order_id}: {inner_e}"
            print(f"CRITICAL ERROR: Failed to restock ticket for order {order_info}")

        # You should log this error e
        return redirect(
            "orders:payment_cancel", order_id=order_id
        )  # Show the cancel page


def payment_success(request, order_id):
    """
    This page is shown when Stripe redirects the user back after a
    successful payment. This page should NOT fulfill the order.
    The webhook does that. This just says "Thanks".
    """
    order = get_object_or_404(Order, id=order_id)
    return render(request, "orders/payment_success.html", {"order": order})


def payment_cancel(request, order_id):
    """
    This page is shown when the user cancels the payment
    or if an error occurred.
    """
    order = get_object_or_404(Order, id=order_id)
    order_failed(order)
    event = order.ticket_info.event
    return render(request, "orders/payment_cancel.html", {"event": event})


@csrf_exempt  # Exempt from CSRF token, as Stripe is posting to this
def stripe_webhook(request):
    """
    Stripe's server-to-server webhook handler.
    This is the only reliable way to know a payment succeeded.
    """
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")
    event = None

    # Use the webhook secret from settings.py
    endpoint_secret = settings.STRIPE.get("STRIPE_WEBHOOK_SECRET", "")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except ValueError:
        # Invalid payload
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError:
        # Invalid signature
        return HttpResponse(status=400)

    print("event['type']:", event["type"])

    # Get the environment this event was *created* in
    session = event["data"]["object"]
    event_env = session.get("metadata", {}).get("environment")

    # Get the environment this *server* is in
    server_env = os.getenv("ENVIRONMENT")

    if event_env != server_env:
        # This event is not for me. Ignore it.
        return HttpResponse(status=200, content=f"OK (Ignored: event for {event_env})")

    def order_failed_handler(session_obj):
        try:
            order_id = session_obj.get("metadata", {}).get("order_id")
            order_obj = Order.objects.get(id=order_id)
            order_failed(order_obj)
        except Order.DoesNotExist:
            print(f"ERROR: Order {order_id} not found in webhook.")
        except Exception as e:
            print(f"ERROR fulfilling order {order_id}: {e}")
            # You should email yourself an error alert here
            return HttpResponse(status=500)

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]

        # Get the order_id we passed in metadata
        order_id = session.get("metadata", {}).get("order_id")

        # Check that the payment was successful
        if session.get("payment_status") == "paid":
            try:
                order = Order.objects.get(id=order_id)

                # Check that we haven't already fulfilled this order
                if order.status == "pending":
                    # 1. MARK ORDER AS COMPLETED
                    order.status = "completed"

                    # 2. SAVE CUSTOMER INFO FROM STRIPE
                    billing_info = BillingInfo.objects.create(
                        full_name=session["customer_details"]["name"],
                        email=session["customer_details"]["email"],
                        phone=session["customer_details"]["phone"] or "",
                    )
                    order.billing_info = billing_info
                    order.save()

                    # 3. FULFILL THE ORDER: CREATE THE TICKET VIA TICKET SERVICES
                    #    This mirrors the tickets.payment_confirm endpoint.
                    created_tickets = []
                    for _ in range(order.quantity):
                        ticket = ticket_services.issue_ticket_for_order(
                            order_id=str(order.id),
                            ticket_info=order.ticket_info,
                            full_name=order.full_name,
                            email=order.email,
                            phone=order.phone,
                            attendee=order.attendee,
                        )
                        created_tickets.append(ticket)

                    # 4. BUILD PDF AND SEND TICKET EMAIL (WITH PDF + QR)
                    try:
                        pdf_bytes = ticket_services.build_tickets_pdf(created_tickets)
                        ticket_services.send_ticket_email(
                            order.email,
                            created_tickets,
                            pdf_bytes=pdf_bytes,
                        )
                    except Exception as e:
                        # Don't break the webhook if email sending fails
                        print(f"Error sending ticket email for order {order.id}: {e}")

            except Order.DoesNotExist:
                print(f"ERROR: Order {order_id} not found in webhook.")
            except Exception as e:
                print(f"ERROR fulfilling order {order_id}: {e}")
                # You should email yourself an error alert here
                return HttpResponse(status=500)
        else:
            session = event["data"]["object"]
            response = order_failed_handler(session)
            if response is not None:
                return response

    # Handle abandoned/expired payment session
    elif event["type"] == "checkout.session.expired":
        session = event["data"]["object"]
        response = order_failed_handler(session)
        if response is not None:
            return response

    elif event["type"] == "refund.updated":
        refund = event["data"]["object"]
        order_id = refund.get("metadata", {}).get("order_id")
        status = refund.get("status")

        # Get the specific amount of *this* refund (in cents)
        amount_refunded_cents = refund.get("amount", 0)

        if order_id and status == "succeeded":
            try:
                with transaction.atomic():
                    # Lock the order
                    order = Order.objects.select_for_update().get(id=order_id)

                    # Process if we are expecting a refund or it's already done/partial
                    if order.status in [
                        "refund_processing",
                        "completed",
                        "partially_refunded",
                        "refunded",
                    ]:

                        # 1. Update the total refunded amount
                        refund_amount_decimal = Decimal(amount_refunded_cents) / 100
                        order.amount_refunded = (
                            order.amount_refunded or Decimal(0)
                        ) + refund_amount_decimal

                        # 2. Determine the new status
                        # Calculate total order cost
                        total_order_cost = order.total_price
                        if order.amount_refunded >= total_order_cost:
                            order.status = "refunded"
                            tickets_to_restock = order.quantity
                        else:
                            order.status = "partially_refunded"
                            tickets_to_restock = 0

                        order.save()

                        event_is_cancelled = False
                        if order.ticket_info and order.ticket_info.event:
                            event_is_cancelled = order.ticket_info.event.is_cancelled

                        # Only restock if the event is NOT cancelled
                        if not event_is_cancelled:
                            if tickets_to_restock > 0:
                                ticket_info = (
                                    TicketInfo.objects.select_for_update().get(
                                        id=order.ticket_info.id
                                    )
                                )
                                ticket_info.availability += tickets_to_restock
                                ticket_info.save()
                        else:
                            print(
                                (
                                    f"Skipping restock for Order {order.id} "
                                    "because Event is cancelled."
                                )
                            )

                        try:
                            # We pass the order and the specific amount
                            # refunded *this time*
                            send_refund_email(order, refund_amount_decimal)
                        except Exception as e:
                            # Log error but don't crash the webhook
                            # (refund is already recorded)
                            print(
                                f"Error sending refund email for order {order.id}: {e}"
                            )

            except Order.DoesNotExist:
                print(f"Refund webhook error: Order {order_id} not found.")
            except Exception as e:
                print(f"Error processing refund webhook for order {order_id}: {e}")
                return HttpResponse(status=500)
    else:
        # Handle other event types
        print(f"Unhandled event type: {event['type']}")

    # Tell Stripe you received the event
    return HttpResponse(status=200)


@custom_login_required(extra_params={"role": "organizer"})
@organizer_owns_event
def event_order_list(request, event_id):
    """
    Display a list of orders for a specific event to the organizer.
    Allows selection of orders for refunds.
    """
    event = get_object_or_404(Event, id=event_id)

    # Check permissions (Simplistic check: Ensure user is authenticated)
    # Ideally check if request.user.organizerprofile owns this event

    # Get all COMPLETED or REFUNDED orders for this event
    orders = Order.objects.filter(
        ticket_info__event=event,
        status__in=["completed", "refunded", "refund_processing", "partially_refunded"],
    ).order_by("-created_at")

    if request.method == "POST":
        selected_order_ids = request.POST.getlist("selected_orders")
        action = request.POST.get("action")

        if not selected_order_ids:
            messages.warning(request, "No orders selected.")
            return redirect("orders:event_order_list", event_id=event.id)

        if action == "refund_full":
            stripe.api_key = settings.STRIPE.get("STRIPE_SECRET_KEY", "")
            success_count = 0

            for order_id in selected_order_ids:
                try:
                    with transaction.atomic():
                        # Lock the order row to prevent race conditions
                        order = Order.objects.select_for_update().get(
                            id=order_id, ticket_info__event=event
                        )

                        print(
                            "order.amount_refunded refund_full", (order.amount_refunded)
                        )
                        # Only refund if currently paid ('completed')
                        # and has a session ID
                        if order.status == "completed" and order.stripe_session_id:

                            # 1. Get PaymentIntent from Stripe Session
                            session = stripe.checkout.Session.retrieve(
                                order.stripe_session_id
                            )
                            payment_intent_id = session.payment_intent

                            if payment_intent_id:
                                # 2. Issue Refund via Stripe API
                                stripe.Refund.create(
                                    payment_intent=payment_intent_id,
                                    reason="requested_by_customer",
                                    metadata={
                                        "order_id": order.id,
                                        "environment": os.getenv(
                                            "ENVIRONMENT", "development"
                                        ),
                                    },
                                )

                                order.status = "refund_processing"
                                order.save()

                                success_count += 1

                except stripe.error.StripeError as e:
                    print(f"Stripe API Error for order {order_id}: {e.user_message}")
                    messages.error(
                        request, f"Stripe Error for Order #{order_id}: {e.user_message}"
                    )

                except Exception as e:
                    print(f"System Error for order {order_id}: {e}")
                    messages.error(
                        request, f"System Error refunding Order #{order_id}."
                    )

            if success_count > 0:
                messages.success(
                    request, "Refund is being processed. Check later for result."
                )
            else:
                messages.error(request, "No eligible orders were refunded.")

        elif action == "refund_partial":
            stripe.api_key = settings.STRIPE.get("STRIPE_SECRET_KEY", "")

            try:
                percentage = int(request.POST.get("refund_percentage", 0))
            except (ValueError, TypeError):
                percentage = 0

            if percentage not in range(10, 91, 10):  # Validate 10-90
                messages.error(
                    request, "Please select a valid refund percentage (10% - 90%)."
                )
                return redirect("orders:event_order_list", event_id=event.id)

            success_count = 0

            for order_id in selected_order_ids:
                try:
                    with transaction.atomic():
                        order = Order.objects.select_for_update().get(
                            id=order_id, ticket_info__event=event
                        )

                        # Can refund if completed or partially refunded
                        if (
                            order.status in ["completed", "partially_refunded"]
                            and order.stripe_session_id
                        ):

                            # Calculate Total Order Price (Unit Price * Quantity)
                            total_order_price = order.price_at_purchase * order.quantity

                            # Calculate refund amount based on Total Price
                            refund_amount = total_order_price * (
                                Decimal(percentage) / Decimal(100)
                            )

                            # Round to 2 decimal places
                            refund_amount = refund_amount.quantize(Decimal("0.01"))
                            refund_amount_cents = int(refund_amount * 100)

                            # Check if this exceeds the total price (100%)
                            current_refunded = order.amount_refunded or Decimal(0)

                            if (current_refunded + refund_amount) > total_order_price:
                                # Calculate max possible percentage
                                remaining_amount = total_order_price - current_refunded
                                if total_order_price > 0:
                                    max_percentage = int(
                                        (remaining_amount / total_order_price) * 100
                                    )
                                else:
                                    max_percentage = 0

                                messages.error(
                                    request,
                                    f"Stopped at Order #{order.id}: "
                                    f"Cannot refund {percentage}%. "
                                    f"Previous refunds total ${current_refunded}. "
                                    f"At most {max_percentage}% can be refunded.",
                                )
                                continue

                            session = stripe.checkout.Session.retrieve(
                                order.stripe_session_id
                            )
                            payment_intent_id = session.payment_intent

                            if payment_intent_id:
                                stripe.Refund.create(
                                    payment_intent=payment_intent_id,
                                    amount=refund_amount_cents,
                                    metadata={
                                        "order_id": order.id,
                                        "environment": os.getenv(
                                            "ENVIRONMENT", "development"
                                        ),
                                    },
                                )

                                order.status = "refund_processing"
                                order.save()
                                success_count += 1

                except stripe.error.StripeError as e:
                    # Capture specific Stripe errors
                    # (Insufficient funds, Charge already refunded)
                    print(f"Stripe API Error for order {order_id}: {e.user_message}")
                    messages.error(
                        request, f"Stripe Error for Order #{order_id}: {e.user_message}"
                    )

                except Exception as e:
                    # Capture other system errors
                    print(f"System Error for order {order_id}: {e}")
                    messages.error(
                        request,
                        f"System Error processing refund for Order #{order_id}.",
                    )

            if success_count > 0:
                messages.success(
                    request,
                    (
                        f"Partial refund initiated for {success_count} orders. "
                        "Check again later for result."
                    ),
                )
            else:
                messages.error(request, "No orders were refunded.")

        return redirect("orders:event_order_list", event_id=event.id)

    context = {
        "event": event,
        "orders": orders,
    }
    return render(request, "orders/event_order_list.html", context)
