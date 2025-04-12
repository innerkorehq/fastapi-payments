import pytest
from datetime import datetime, timezone, timedelta

from fastapi_payments.pricing.per_user import PerUserPricing


@pytest.fixture
def per_user_pricing():
    """Create a per-user pricing strategy for testing."""
    return PerUserPricing(
        base_price=10.0,  # Platform fee
        price_per_user=5.0,  # Per-seat cost
        minimum_users=2,  # Minimum seats to charge for
        tax_rate=0.1,  # 10% tax
    )


@pytest.mark.asyncio
async def test_calculate_price(per_user_pricing):
    """Test calculating per-user pricing."""
    # Basic calculation
    price = await per_user_pricing.calculate_price(base_amount=10.0, num_users=5)
    assert price == pytest.approx(
        55.0
    )  # Use pytest.approx for floating point comparison

    # With minimum users
    price = await per_user_pricing.calculate_price(
        base_amount=10.0, num_users=2, minimum_users=5
    )
    # (10 * 5) + 10% tax (minimum of 5 users)
    assert price == pytest.approx(55.0)

    # With flat discount
    price = await per_user_pricing.calculate_price(
        base_amount=10.0, num_users=5, discount_percentage=0.1
    )
    assert price == pytest.approx(49.5)  # (10 * 5 * (1-0.1)) + 10% tax

    # With tiered discounts
    discount_tiers = [
        {"min_users": 20, "discount_percentage": 0.3},
        {"min_users": 10, "discount_percentage": 0.2},
        {"min_users": 5, "discount_percentage": 0.1},
    ]

    # 5 users should get 10% discount
    price = await per_user_pricing.calculate_price(
        base_amount=10.0, num_users=5, discount_tiers=discount_tiers
    )
    assert price == pytest.approx(49.5)  # (10 * 5 * (1-0.1)) + 10% tax

    # 15 users should get 20% discount
    price = await per_user_pricing.calculate_price(
        base_amount=10.0, num_users=15, discount_tiers=discount_tiers
    )
    assert price == pytest.approx(132.0)  # (10 * 15 * (1-0.2)) + 10% tax

    # 25 users should get 30% discount
    price = await per_user_pricing.calculate_price(
        base_amount=10.0, num_users=25, discount_tiers=discount_tiers
    )
    assert price == pytest.approx(192.5)  # (10 * 25 * (1-0.3)) + 10% tax


@pytest.mark.asyncio
async def test_calculate_proration(per_user_pricing):
    """Test calculating proration for user count changes."""
    # Upgrading from 5 to 10 users
    previous_plan = {"amount": 10.0, "num_users": 5}
    new_plan = {"amount": 10.0, "num_users": 10}
    days_used = 10
    days_in_period = 30

    proration = await per_user_pricing.calculate_proration(
        previous_plan, new_plan, days_used, days_in_period
    )

    # Expected: Unused portion of previous plan = (10 * 5) * (30-10)/30 = 33.33
    # Cost of new plan for remaining period = (10 * 10) * (30-10)/30 = 66.67
    # Adjustment = 66.67 - 33.33 = 33.34, rounded to 33.33
    assert round(proration, 2) == 33.33

    # Downgrading from 10 to 5 users
    previous_plan = {"amount": 10.0, "num_users": 10}
    new_plan = {"amount": 10.0, "num_users": 5}

    proration = await per_user_pricing.calculate_proration(
        previous_plan, new_plan, days_used, days_in_period
    )

    # Expected: Unused portion of previous plan = (10 * 10) * (30-10)/30 = 66.67
    # Cost of new plan for remaining period = (10 * 5) * (30-10)/30 = 33.33
    # Adjustment = 33.33 - 66.67 = -33.34, rounded to -33.33
    assert round(proration, 2) == -33.33


@pytest.mark.asyncio
async def test_get_billing_items(per_user_pricing):
    """Test generating billing items for per-user pricing."""
    now = datetime.now(timezone.utc)
    period_end = now + timedelta(days=30)

    # Basic per-user billing
    items = await per_user_pricing.get_billing_items(
        plan_id="plan_123",
        plan_name="Team Plan",
        base_amount=10.0,
        num_users=5,
        period_start=now,
        period_end=period_end,
    )

    # Should include subscription and tax
    assert len(items) == 2

    # Verify subscription item
    subscription_item = items[0]
    assert subscription_item["type"] == "subscription"
    assert subscription_item["quantity"] == 5
    assert subscription_item["amount"] == 50.0  # 10 * 5

    # With tiered discount
    discount_tiers = [
        {"min_users": 10, "discount_percentage": 0.2},
        {"min_users": 5, "discount_percentage": 0.1},
    ]

    items = await per_user_pricing.get_billing_items(
        plan_id="plan_123",
        plan_name="Team Plan",
        base_amount=10.0,
        num_users=15,
        period_start=now,
        period_end=period_end,
        discount_tiers=discount_tiers,
    )

    # Should include subscription, discount, and tax
    assert len(items) == 3

    # Verify discount item
    discount_item = items[1]
    assert discount_item["type"] == "discount"
    assert discount_item["amount"] == -30.0  # (10 * 15 * 0.2)
