import pytest
from django.db.models import ProtectedError
from decimal import Decimal


# Mark all tests in this file as needing database access
pytestmark = pytest.mark.django_db


def test_billing_info_str(billing_info):
    """Test the string representation of the BillingInfo model."""
    expected_str = "Test Billing - billing@example.com - 123-456-7890"
    assert str(billing_info) == expected_str


def test_order_creation_save_and_str(order, ticket_info_ga):
    """
    Tests two things:
    1. The custom save() method correctly sets 'price_at_purchase' on creation.
    2. The __str__ method formats correctly.
    """
    # Test 1: Check custom save() logic (price_at_purchase)
    # The 'order' fixture already triggered the .save() on create
    assert order.price_at_purchase == ticket_info_ga.price
    assert order.price_at_purchase == Decimal("50.00")

    # Test 2: Check __str__ method
    t_info = f"{order.quantity} x General Admission for Test Order User"
    expected_str = f"Order {order.id} (pending) - {t_info}"
    assert str(order) == expected_str


def test_order_update_does_not_change_price(order, ticket_info_ga):
    """
    Test that 'price_at_purchase' is NOT updated on a subsequent save(),
    even if the source ticket_info price changes.
    """
    original_price = order.price_at_purchase
    assert original_price == Decimal("50.00")

    # Modify the source ticket price
    ticket_info_ga.price = Decimal("999.00")
    ticket_info_ga.save()

    # Save the order again (e.g., to change status)
    order.status = "completed"
    order.save()
    order.refresh_from_db()

    # Assert that the price_at_purchase did NOT change
    assert order.status == "completed"
    assert order.price_at_purchase == original_price


def test_order_protects_ticket_info_deletion(order, ticket_info_ga):
    """
    Test that on_delete=models.PROTECT prevents the deletion
    of a TicketInfo that is linked to an Order.
    """
    # We expect a ProtectedError when trying to delete the ticket_info_ga
    with pytest.raises(ProtectedError):
        ticket_info_ga.delete()


def test_order_protects_billing_info_deletion(order, billing_info):
    """
    Test that on_delete=models.PROTECT prevents the deletion
    of a BillingInfo that is linked to an Order.
    """
    # We expect a ProtectedError when trying to delete the billing_info
    with pytest.raises(ProtectedError):
        billing_info.delete()
