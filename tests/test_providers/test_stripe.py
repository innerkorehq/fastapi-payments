import pytest
import json
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone

from fastapi_payments.providers.stripe import StripeProvider
from fastapi_payments.config.config_schema import ProviderConfig


@pytest.fixture
def stripe_provider():
    """Create a test Stripe provider."""
    config = ProviderConfig(
        api_key="sk_test_mock_key",
        webhook_secret="whsec_mock_secret",
        sandbox_mode=True,
    )

    provider = StripeProvider(config)

    # Mock stripe client
    provider.stripe = MagicMock()

    return provider


@pytest.mark.asyncio
async def test_create_customer(stripe_provider):
    """Test creating a customer in Stripe."""
    email = "test@example.com"
    name = "Test Customer"

    result = await stripe_provider.create_customer(email, name)

    assert result["email"] == email
    assert result["name"] == name
    assert "provider_customer_id" in result
    assert "created_at" in result


@pytest.mark.asyncio
async def test_retrieve_customer(stripe_provider):
    """Test retrieving a customer from Stripe."""
    # Create a customer first
    create_result = await stripe_provider.create_customer(
        "test@example.com", "Test Customer"
    )

    # Retrieve the customer
    result = await stripe_provider.retrieve_customer(
        create_result["provider_customer_id"]
    )

    assert "provider_customer_id" in result
    assert "email" in result
    assert "name" in result


@pytest.mark.asyncio
async def test_create_payment_method(stripe_provider):
    """Test creating a payment method in Stripe."""
    # Create a customer first
    customer = await stripe_provider.create_customer(
        "test@example.com", "Test Customer"
    )

    payment_details = {
        "type": "card",
        "card": {
            "number": "4242424242424242",
            "exp_month": 12,
            "exp_year": 2030,
            "cvc": "123",
        },
    }

    result = await stripe_provider.create_payment_method(
        customer["provider_customer_id"], payment_details
    )

    assert "payment_method_id" in result
    assert result["type"] == "card"
    assert "card" in result


@pytest.mark.asyncio
async def test_create_product(stripe_provider):
    """Test creating a product in Stripe."""
    result = await stripe_provider.create_product(
        name="Test Product", description="A test product"
    )

    assert "provider_product_id" in result
    assert result["name"] == "Test Product"
    assert result["description"] == "A test product"
    assert result["active"] is True


@pytest.mark.asyncio
async def test_create_price(stripe_provider):
    """Test creating a price in Stripe."""
    # Create a product first
    product = await stripe_provider.create_product("Test Product")

    result = await stripe_provider.create_price(
        product_id=product["provider_product_id"],
        amount=19.99,
        currency="USD",
        interval="month",
        interval_count=1,
    )

    assert "provider_price_id" in result
    assert result["product_id"] == product["provider_product_id"]
    assert result["amount"] == 19.99
    assert result["currency"] == "USD"
    assert "recurring" in result
    assert result["recurring"]["interval"] == "month"


@pytest.mark.asyncio
async def test_create_subscription(stripe_provider):
    """Test creating a subscription in Stripe."""
    # Create a customer first
    customer = await stripe_provider.create_customer(
        "test@example.com", "Test Customer"
    )

    # Create a product
    product = await stripe_provider.create_product("Test Product")

    # Create a price
    price = await stripe_provider.create_price(
        product_id=product["provider_product_id"],
        amount=19.99,
        currency="USD",
        interval="month",
    )

    result = await stripe_provider.create_subscription(
        provider_customer_id=customer["provider_customer_id"],
        price_id=price["provider_price_id"],
        quantity=2,
    )

    assert "provider_subscription_id" in result
    assert result["customer_id"] == customer["provider_customer_id"]
    assert result["price_id"] == price["provider_price_id"]
    assert result["quantity"] == 2
    assert result["status"] == "active"


@pytest.mark.asyncio
async def test_process_payment(stripe_provider):
    """Test processing a payment with Stripe."""
    # Create a customer first
    customer = await stripe_provider.create_customer(
        "test@example.com", "Test Customer"
    )

    result = await stripe_provider.process_payment(
        amount=100.00,
        currency="USD",
        provider_customer_id=customer["provider_customer_id"],
        description="Test payment",
    )

    assert "provider_payment_id" in result
    assert result["amount"] == 100.00
    assert result["currency"] == "USD"
    assert result["status"] == "succeeded"
    assert result["description"] == "Test payment"


@pytest.mark.asyncio
async def test_webhook_handler(stripe_provider):
    """Test handling a webhook from Stripe."""
    # Test a payment succeeded event
    event_data = {
        "id": "evt_test",
        "type": "payment_intent.succeeded",
        "data": {
            "object": {
                "id": "pi_test",
                "amount": 1000,
                "currency": "usd",
                "customer": "cus_test",
            }
        },
    }

    result = await stripe_provider.webhook_handler(payload=event_data)

    assert result["event_type"] == "payment_intent.succeeded"
    assert result["standardized_event_type"] == "payment.succeeded"
    assert result["provider"] == "stripe"
