import pytest
from datetime import datetime, timedelta

from fastapi_payments.pricing.tiered import TieredPricing


@pytest.fixture
def tiered_pricing():
    """Create a tiered pricing strategy for testing."""
    tiers = [
        {"min": 0, "max": 10, "unit_price": 10.0, "flat_fee": 5.0},
        {"min": 11, "max": 20, "unit_price": 8.0, "flat_fee": 0.0},
        {"min": 21, "max": None, "unit_price": 5.0},  # No upper limit
    ]
    return TieredPricing(tiers, tax_rate=0.1)


def test_calculate_price(tiered_pricing):
    """Test tiered pricing calculation."""
    # First tier only
    price = tiered_pricing.calculate_price(usage=5)
    # (5*10 + 5 flat fee) * 1.1 = 60.5
    assert price == pytest.approx(60.5, rel=1e-4)

    # Exactly at first tier limit
    price = tiered_pricing.calculate_price(usage=10)
    # (10*10 + 5 flat fee) * 1.1 = 115.5
    assert price == pytest.approx(115.5, rel=1e-4)

    # Second tier only
    price = tiered_pricing.calculate_price(usage=15)
    # (10*10 + 5 + 5*8) * 1.1 = 132.0
    assert price == pytest.approx(132.0, rel=1e-4)

    # Multiple tiers
    price = tiered_pricing.calculate_price(usage=25)
    assert price == pytest.approx(
        187.0, rel=1e-4
    )  # (10*10 + 5 + 10*8 + 5*5) * 1.1 = 187.0

    # Custom tax rate
    price = tiered_pricing.calculate_price(usage=5, tax_rate=0.2)
    assert price == pytest.approx(66.0, rel=1e-4)  # (5*10 + 5) * 1.2 = 66.0


def test_get_billing_items(tiered_pricing):
    """Test tiered billing items."""
    # First tier only
    items = tiered_pricing.get_billing_items(usage=5)
    assert len(items) == 2  # Flat fee + usage
    assert items[0]["description"] == "Tier 0-10 flat fee"
    assert items[0]["amount"] == 5.0
    assert items[1]["description"] == "Tier 0-10 usage (5 units)"
    assert items[1]["amount"] == 50.0  # 5 * 10.0

    # Multiple tiers
    items = tiered_pricing.get_billing_items(usage=25)
    assert (
        len(items) == 4
    )  # Tier 1 flat fee + Tier 1 usage + Tier 2 usage + Tier 3 usage
    assert items[0]["description"] == "Tier 0-10 flat fee"
    assert items[1]["description"] == "Tier 0-10 usage (10 units)"
    assert items[2]["description"] == "Tier 11-20 usage (10 units)"
    assert items[3]["description"] == "Tier 21-∞ usage (5 units)"
    assert items[3]["amount"] == 25.0  # 5 * 5.0
