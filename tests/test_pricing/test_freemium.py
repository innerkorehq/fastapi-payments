import pytest
from datetime import datetime, timedelta

from fastapi_payments.pricing.freemium import FreemiumPricing


@pytest.fixture
def freemium_pricing():
    """Create a freemium pricing strategy."""
    return FreemiumPricing(
        base_price=0.0, free_tier_limit=100, paid_tier_price=19.99, tax_rate=0.1
    )


def test_calculate_price_free_tier(freemium_pricing):
    """Test free tier pricing (below limit)."""
    # Usage within free tier limit should result in zero cost
    price = freemium_pricing.calculate_price(usage=50)
    assert price == 0.0

    # Edge case: exactly at free tier limit
    price = freemium_pricing.calculate_price(usage=100)
    assert price == 0.0


def test_calculate_price_paid_tier(freemium_pricing):
    """Test paid tier pricing (above free limit)."""
    # Exceeding free tier limit should result in paid tier price
    price = freemium_pricing.calculate_price(usage=101)
    # Use pytest.approx for floating point comparison
    assert price == pytest.approx(21.989, rel=1e-4)  # 19.99 + 10% tax

    # Different tax rate
    price = freemium_pricing.calculate_price(usage=101, tax_rate=0.2)
    assert price == pytest.approx(23.988, rel=1e-4)  # 19.99 + 20% tax


def test_calculate_proration(freemium_pricing):
    """Test proration for freemium pricing."""
    # Free tier proration should be 0 regardless of days used
    proration = freemium_pricing.calculate_proration(
        days_used=15, days_in_period=30, usage=50
    )
    assert proration == 0.0

    # Paid tier should be prorated
    proration = freemium_pricing.calculate_proration(
        days_used=15, days_in_period=30, usage=150
    )
    assert proration == 9.995  # 19.99 * (15/30)
