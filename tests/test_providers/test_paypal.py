import pytest
from unittest.mock import AsyncMock
from tests.fakes.fake_paypal import paypal_provider


@pytest.mark.asyncio
async def test_create_customer(paypal_provider):
    """Test creating a customer with PayPal."""
    result = await paypal_provider.create_customer(
        email="test@example.com", name="Test User"
    )

    assert result["provider_customer_id"] == "CUSTOMER-ID-1234"
    assert result["email"] == "test@example.com"
    assert "created_at" in result


@pytest.mark.asyncio
async def test_create_product(paypal_provider):
    """Test creating a product with PayPal."""
    result = await paypal_provider.create_product(
        name="Test Product", description="A test product"
    )

    assert result["provider_product_id"] == "PROD-1234"
    assert result["name"] == "Test Product"
    assert result["description"] == "A test product"


@pytest.mark.asyncio
async def test_create_price(paypal_provider):
    """Test creating a price/plan with PayPal."""
    result = await paypal_provider.create_price(
        product_id="PROD-1234",
        amount=19.99,
        currency="USD",
        interval="month",
        interval_count=1,
    )

    assert result["provider_price_id"] == "PLAN-1234"
    assert result["product_id"] == "PROD-1234"
    assert "created_at" in result


@pytest.mark.asyncio
async def test_create_subscription(paypal_provider):
    """Test creating a subscription with PayPal."""
    result = await paypal_provider.create_subscription(
        provider_customer_id="CUSTOMER-ID-1234", price_id="PLAN-1234"
    )

    assert result["provider_subscription_id"] == "SUB-1234"
    assert result["status"] == "active"
    assert "current_period_start" in result
    assert "current_period_end" in result


@pytest.mark.asyncio
async def test_process_payment(paypal_provider):
    """Test processing a payment with PayPal."""
    result = await paypal_provider.process_payment(
        amount=10.00,
        currency="USD",
        provider_customer_id="CUSTOMER-ID-1234",
        payment_method_id="TOKEN-1234",
        description="Test payment",
    )

    assert result["provider_payment_id"] == "PAY-1234"
    assert result["status"] == "COMPLETED"
    assert result["amount"] == 10.00


@pytest.mark.asyncio
async def test_webhook_handler(paypal_provider):
    """Test handling webhooks from PayPal."""
    webhook_payload = {
        "id": "WH-1234",
        "event_type": "PAYMENT.CAPTURE.COMPLETED",
        "resource": {
            "id": "5O190127TN364715T",
            "status": "COMPLETED",
            "amount": {"total": "10.00", "currency": "USD"},
        },
    }

    # Mock _verify_webhook_signature
    paypal_provider._verify_webhook_signature = AsyncMock(return_value=True)

    result = await paypal_provider.webhook_handler(
        payload=webhook_payload, signature="test_signature"
    )

    assert result["event_type"] == "PAYMENT.CAPTURE.COMPLETED"
    assert result["standardized_event_type"] == "payment.succeeded"
    assert result["data"]["id"] == "5O190127TN364715T"
    assert result["data"]["status"] == "COMPLETED"
