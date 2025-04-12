import pytest
from datetime import datetime, timedelta
from fastapi_payments.pricing.hybrid import HybridPricing


@pytest.mark.asyncio
async def test_hybrid_pricing_calculation(test_config):
    """Test hybrid pricing calculation with both subscription and usage components."""
    # Initialize hybrid pricing with different configurations

    # Base subscription with 10% tax rate
    pricing1 = HybridPricing(base_price=20.0, usage_rate=0.0, tax_rate=0.1)
    price1 = pricing1.calculate_price(quantity=1, usage=0)
    assert price1 == 22.0  # 20.0 + 10% tax

    # Subscription with usage (base price + usage * rate)
    pricing2 = HybridPricing(base_price=20.0, usage_rate=1.0, tax_rate=0.1)
    price2 = pricing2.calculate_price(quantity=1, usage=5)
    assert price2 == 27.5  # (20.0 + 5.0) + 10% tax

    # Multiple subscription units
    pricing3 = HybridPricing(base_price=20.0, usage_rate=0.0, tax_rate=0.1)
    price3 = pricing3.calculate_price(quantity=2, usage=0)
    assert price3 == 44.0  # (20.0 * 2) + 10% tax

    # Custom tax rate
    pricing4 = HybridPricing(base_price=20.0, usage_rate=1.0, tax_rate=0.05)
    price4 = pricing4.calculate_price(quantity=1, usage=5, tax_rate=0.2)
    assert price4 == 30.0  # (20.0 + 5.0) + 20% tax


def test_hybrid_pricing_billing_items():
    """Test billing items for hybrid pricing."""
    pricing = HybridPricing(base_price=20.0, usage_rate=1.0)

    # Test with subscription only
    items1 = pricing.get_billing_items(quantity=1, usage=0)
    assert len(items1) == 1
    subscription_item = items1[0]
    assert subscription_item["description"] == "Subscription (1 units)"
    assert subscription_item["amount"] == 20.0

    # Test with subscription and usage
    items2 = pricing.get_billing_items(quantity=1, usage=5)
    assert len(items2) == 2
    subscription_item = items2[0]
    assert subscription_item["description"] == "Subscription (1 units)"
    assert subscription_item["amount"] == 20.0

    usage_item = items2[1]
    assert usage_item["description"] == "Usage (5 units)"
    assert usage_item["amount"] == 5.0

    # Test with multiple subscription units
    items3 = pricing.get_billing_items(quantity=2, usage=3)
    assert len(items3) == 2
    subscription_item = items3[0]
    assert subscription_item["description"] == "Subscription (2 units)"
    assert subscription_item["amount"] == 40.0

    usage_item = items3[1]
    assert usage_item["description"] == "Usage (3 units)"
    assert usage_item["amount"] == 3.0


def test_hybrid_pricing_proration():
    """Test proration calculations for hybrid pricing."""
    pricing = HybridPricing(base_price=30.0)

    # Test full period
    prorated_amount1 = pricing.calculate_proration(
        days_used=30, days_in_period=30, quantity=1
    )
    assert prorated_amount1 == 30.0  # Full price

    # Test half period
    prorated_amount2 = pricing.calculate_proration(
        days_used=15, days_in_period=30, quantity=1
    )
    assert prorated_amount2 == 15.0  # Half price

    # Test with multiple quantities
    prorated_amount3 = pricing.calculate_proration(
        days_used=15, days_in_period=30, quantity=2
    )
    assert prorated_amount3 == 30.0  # Half price * 2 quantities

    # Test with zero days in period (should return 0)
    prorated_amount4 = pricing.calculate_proration(
        days_used=5, days_in_period=0, quantity=1
    )
    assert prorated_amount4 == 0.0  # Return 0 to avoid division by zero


def test_hybrid_pricing_edge_cases():
    """Test edge cases for hybrid pricing."""
    # Zero base price with usage
    pricing1 = HybridPricing(base_price=0.0, usage_rate=2.0, tax_rate=0.1)
    price1 = pricing1.calculate_price(quantity=1, usage=5)
    assert price1 == 11.0  # (0.0 + 5.0*2.0) + 10% tax

    # Zero usage rate with base price
    pricing2 = HybridPricing(base_price=20.0, usage_rate=0.0, tax_rate=0.1)
    price2 = pricing2.calculate_price(quantity=1, usage=5)
    assert price2 == 22.0  # (20.0 + 0.0) + 10% tax

    # Zero tax rate
    pricing3 = HybridPricing(base_price=20.0, usage_rate=1.0, tax_rate=0.0)
    price3 = pricing3.calculate_price(quantity=1, usage=5)
    assert price3 == 25.0  # (20.0 + 5.0) + 0% tax
