import stripe
from django.db import transaction
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

from .models import Order, BillingInfo
from .forms import OrderForm
from tickets.models import Ticket
from accounts.models import UserProfile
from events.models import Event

# Create your views here.


def order(request, event_id):
    event = get_object_or_404(Event, id=event_id)

    if request.method == "POST":
        # Pass the event object to the form constructor
        form = OrderForm(request.POST, event=event)

        if form.is_valid():
            try:
                # Use a database transaction to ensure data integrity
                with transaction.atomic():
                    # Save the form to create the ticket instance
                    order = form.save(commit=False)
                    order.status='pending'
                    if request.session.get("desired_role") == "attendee":
                        order.attendee = UserProfile.objects.get(user=request.user)
                    order.save()

                    # Decrement the availability of the chosen TicketInfo
                    ticket_info = form.cleaned_data["ticket_info"]
                    ticket_info.availability -= 1
                    ticket_info.save()

                return redirect("orders:process_payment", order_id=order.id)
            except Exception as e:  # pragma: no cover (optional)
                # You may want to log this instead of print in production
                print(e)
    else:
        # For a GET request, pass the event object to the form
        form = OrderForm(event=event)

    return render(
        request,
        "orders/order.html",
        {"event": event, "form": form},
    )

# test card: https://docs.stripe.com/testing
# test link info: https://docs.stripe.com/connect/testing-verification?connect-account-creation-pattern=typed
def process_payment(request, order_id):
    """
    This view is called when the user clicks "Buy Ticket".
    It creates a new 'pending' Order,
    then redirects the user to Stripe to pay.
    """

    order = get_object_or_404(Order, id = order_id)
    event_id = order.ticket_info.event.id

    if order.status != 'pending':
        return redirect('payment_cancel', event_id=event_id)
    
    ticket_info = order.ticket_info

    stripe.api_key = settings.STRIPE_SECRET_KEY

    try:
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': f"{ticket_info.event.title} - {ticket_info.category}",
                    },
                    # Price must be in cents
                    'unit_amount': int(ticket_info.price * 100), 
                },
                'quantity': 1,
            }],
            mode='payment',
            customer_creation='always',  # Creates a Stripe Customer object
            phone_number_collection={
                    'enabled': True,
                },
            # IMPORTANT: Pass the Order ID in metadata
            # This is how our webhook will find the order later
            metadata={
                'order_id': order.id
            },
            # Redirect URLs
            success_url='http://127.0.0.1:8000'+reverse('orders:payment_success', args = [order.id]),
            cancel_url='http://127.0.0.1:8000'+reverse('orders:payment_cancel', args=[order.id]),
        )

        order.stripe_session_id = session.id
        order.save()

        # Redirect the user to Stripe's payment page
        return redirect(session.url, code=303)

    except Exception as e:
        print(f"Stripe Error: {e}")
        # Handle any Stripe errors
        order.status = 'failed'
        order.save()
        # You should log this error e
        return redirect('orders:payment_cancel', order_id=order_id) # Show the cancel page

def payment_success(request, order_id):
    """
    This page is shown when Stripe redirects the user back after a 
    successful payment. This page should NOT fulfill the order.
    The webhook does that. This just says "Thanks".
    """
    order = get_object_or_404(Order, id=order_id)
    return render(request, 'orders/payment_success.html', {"order": order})

def payment_cancel(request, order_id):
    """
    This page is shown when the user cancels the payment
    or if an error occurred.
    """
    order = get_object_or_404(Order, id=order_id)

    ticket_info = order.ticket_info
    ticket_info.availability += 1
    ticket_info.save()

    event = ticket_info.event
    return render(request, 'orders/payment_cancel.html', {"event": event})

@csrf_exempt # Exempt from CSRF token, as Stripe is posting to this
def stripe_webhook(request):
    """
    Stripe's server-to-server webhook handler.
    This is the only reliable way to know a payment succeeded.
    """
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    event = None
    
    # Use the webhook secret from settings.py
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError as e:
        # Invalid payload
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        return HttpResponse(status=400)

    # --- Handle the "checkout.session.completed" event ---
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        
        # Get the order_id we passed in metadata
        order_id = session.get('metadata', {}).get('order_id')
        
        # Check that the payment was successful
        if session.get('payment_status') == 'paid':
            try:
                order = Order.objects.get(id=order_id)
                
                # Check that we haven't already fulfilled this order
                if order.status == 'pending':
                    # 1. MARK ORDER AS COMPLETED
                    order.status = 'completed'
                    
                    # 2. SAVE CUSTOMER INFO FROM STRIPE
                    billing_info = BillingInfo.objects.create(
                        full_name=session['customer_details']['name'],
                        email=session['customer_details']['email'],
                        phone=session['customer_details']['phone'] or ''
                    )
                    order.billing_info = billing_info
                    order.save()
                    
                    # 3. FULFILL THE ORDER: CREATE THE TICKET!
                    Ticket.objects.create(
                        attendee=order.attendee,
                        ticketInfo=order.ticket_info,
                        full_name=order.full_name,
                        email=order.email,
                        phone=order.phone
                    )

            except Order.DoesNotExist:
                print(f"ERROR: Order {order_id} not found in webhook.")
            except Exception as e:
                print(f"ERROR fulfilling order {order_id}: {e}")
                # You should email yourself an error alert here
                return HttpResponse(status=500)
                
    else:
        # Handle other event types (e.g., checkout.session.expired)
        print(f"Unhandled event type: {event['type']}")

    # Tell Stripe you received the event
    return HttpResponse(status=200)