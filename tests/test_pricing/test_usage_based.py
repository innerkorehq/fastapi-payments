import pytest
from datetime import datetime, timedelta

from fastapi_payments.pricing.usage_based import UsageBasedPricing


@pytest.fixture
def usage_pricing():
    """Create a usage-based pricing strategy for testing."""
    return UsageBasedPricing(price_per_unit=0.5, minimum_charge=10.0, tax_rate=0.1)


@pytest.fixture
def capped_usage_pricing():
    """Create a usage-based pricing strategy with maximum charge."""
    return UsageBasedPricing(
        price_per_unit=0.5, minimum_charge=10.0, maximum_charge=50.0, tax_rate=0.1
    )


def test_calculate_price(usage_pricing):
    """Test usage-based pricing calculation."""
    # Below minimum charge threshold
    price = usage_pricing.calculate_price(usage=10)
    assert (
        price == 11.0
    )  # 10.0 minimum * 1.1 = 11.0 (10 units would be 5.0, below minimum)

    # Above minimum charge threshold
    price = usage_pricing.calculate_price(usage=30)
    assert price == 16.5  # 30 * 0.5 * 1.1 = 16.5

    # With custom tax rate
    price = usage_pricing.calculate_price(usage=30, tax_rate=0.2)
    assert price == 18.0  # 30 * 0.5 * 1.2 = 18.0


def test_get_billing_items(usage_pricing):
    """Test usage-based billing items."""
    # Below minimum charge
    items = usage_pricing.get_billing_items(usage=10)
    assert len(items) == 2
    assert items[0]["description"] == "Usage (10 units)"
    assert items[0]["amount"] == 5.0  # 10 * 0.5
    assert items[1]["description"] == "Minimum charge adjustment"
    # 10.0 minimum - 5.0 usage = 5.0 adjustment
    assert items[1]["amount"] == 5.0

    # Above minimum charge
    items = usage_pricing.get_billing_items(usage=30)
    assert len(items) == 1
    assert items[0]["description"] == "Usage (30 units)"
    assert items[0]["amount"] == 15.0  # 30 * 0.5


def test_minimum_maximum_charge(capped_usage_pricing):
    """Test minimum and maximum charge constraints."""
    # Below minimum charge
    price = capped_usage_pricing.calculate_price(usage=10)
    assert price == pytest.approx(11.0, rel=1e-4)  # 10.0 minimum * 1.1 = 11.0

    # Above maximum charge
    price = capped_usage_pricing.calculate_price(usage=200)
    assert price == pytest.approx(
        55.0, rel=1e-4
    )  # 50.0 maximum * 1.1 = 55.0 (200 units would be 100.0, above maximum)

    # Maximum charge with custom tax
    price = capped_usage_pricing.calculate_price(usage=200, tax_rate=0.2)
    assert price == pytest.approx(60.0, rel=1e-4)  # 50.0 maximum * 1.2 = 60.0

    # Test billing items with maximum charge constraint
    items = capped_usage_pricing.get_billing_items(usage=200)
    assert len(items) == 2
    assert items[0]["description"] == "Usage (200 units)"
    assert items[0]["amount"] == 100.0  # 200 * 0.5
    assert items[1]["description"] == "Maximum charge adjustment"
    # 50.0 maximum - 100.0 usage = -50.0 adjustment
    assert items[1]["amount"] == -50.0
