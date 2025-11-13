import os
import time
import stripe
from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt

from accounts.models import UserProfile
from events.models import Event
from tickets.models import TicketInfo
from tickets import services as ticket_services
from .forms import OrderForm
from .models import BillingInfo, Order


def order(request, event_id):
    event = get_object_or_404(Event, id=event_id)

    if request.method == "POST":
        # Pass the event object to the form constructor
        form = OrderForm(request.POST, event=event)

        if form.is_valid():
            try:
                # Use a database transaction to ensure data integrity
                with transaction.atomic():
                    # Decrement the availability of the chosen TicketInfo
                    ticket_info = form.cleaned_data["ticket_info"]
                    ticket_info = TicketInfo.objects.select_for_update().get(
                        id=ticket_info.id
                    )
                    quantity = form.cleaned_data["quantity"]

                    if ticket_info.availability < 1:
                        messages.error(request, "Sorry, this ticket is now sold out.")
                        return redirect("orders:order", event_id=event.id)

                    ticket_info.availability -= quantity
                    ticket_info.save()

                    # Save the form to create the order instance
                    order = form.save(commit=False)
                    if request.session.get("desired_role") == "attendee":
                        order.attendee = UserProfile.objects.get(user=request.user)
                    order.save()

                return redirect("orders:process_payment", order_id=order.id)
            except Exception as e:  # pragma: no cover (optional)
                # You may want to log this instead of print in production
                print(e)
    else:
        # For a GET request, pass the event object to the form
        form = OrderForm(event=event)

    available_tickets = TicketInfo.objects.filter(event=event, availability__gt=0)
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
    else:
        # Handle other event types
        print(f"Unhandled event type: {event['type']}")

    # Tell Stripe you received the event
    return HttpResponse(status=200)
