import pytest


def calculate_subscription_price(base_price, quantity, tax_rate):
    """Calculate the subscription price."""
    subtotal = base_price * quantity
    tax = subtotal * tax_rate
    return subtotal + tax


def test_calculate_price():
    """Test price calculation."""
    base_price = 66.0
    quantity = 1
    tax_rate = 0.2  # 20%

    # Calculate price
    total = calculate_subscription_price(base_price, quantity, tax_rate)

    # Expected: base_price * quantity * (1 + tax_rate)
    expected = 66.0 * 1 * 1.2
    assert total == 79.2
