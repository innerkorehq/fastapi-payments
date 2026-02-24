"""Tests for Razorpay payment provider."""

import pytest
from unittest.mock import patch, MagicMock
import json

from fastapi_payments.config.config_schema import ProviderConfig
from fastapi_payments.providers.razorpay import RazorpayProvider
from tests.fakes.fake_razorpay import FakeRazorpay


@pytest.fixture
def fake_razorpay():
    """Create a fake Razorpay instance."""
    return FakeRazorpay()


@pytest.fixture
def razorpay_provider(fake_razorpay):
    """Create a Razorpay provider instance with mocked client."""
    config = ProviderConfig(
        api_key="test_key_id",
        api_secret="test_key_secret",
        sandbox_mode=True,
        webhook_secret="test_webhook_secret",
        additional_settings={
            "return_url": "https://merchant.test/return",
            "notify_url": "https://merchant.test/webhook",
            "default_currency": "INR",
        },
    )
    
    # Mock the razorpay import
    with patch.dict('sys.modules', {'razorpay': MagicMock()}):
        provider = RazorpayProvider(config)
        # Replace the client with our fake
        provider.client = fake_razorpay
        provider._razorpay = MagicMock()
    
    return provider


@pytest.mark.asyncio
async def test_create_customer(razorpay_provider):
    """Test customer creation."""
    result = await razorpay_provider.create_customer(
        email="test@example.com",
        name="Test Customer",
        meta_info={"phone": "9999999999"},
        address={
            "line1": "123 Test St",
            "city": "Mumbai",
            "state": "Maharashtra",
            "postal_code": "400001",
            "country": "IN",
        },
    )
    
    assert result["email"] == "test@example.com"
    assert result["name"] == "Test Customer"
    assert "provider_customer_id" in result
    assert result["provider_customer_id"].startswith("cust_")
    assert "contact" in result["meta_info"]


@pytest.mark.asyncio
async def test_retrieve_customer(razorpay_provider, fake_razorpay):
    """Test customer retrieval."""
    # First create a customer
    created = await razorpay_provider.create_customer(
        email="test@example.com",
        name="Test Customer",
    )
    
    # Then retrieve it
    result = await razorpay_provider.retrieve_customer(
        created["provider_customer_id"]
    )
    
    assert result["provider_customer_id"] == created["provider_customer_id"]
    assert result["email"] == "test@example.com"


@pytest.mark.asyncio
async def test_update_customer(razorpay_provider):
    """Test customer update."""
    # First create a customer
    created = await razorpay_provider.create_customer(
        email="test@example.com",
        name="Test Customer",
    )
    
    # Update the customer
    result = await razorpay_provider.update_customer(
        created["provider_customer_id"],
        {"name": "Updated Name", "email": "updated@example.com"},
    )
    
    assert result["name"] == "Updated Name"
    assert result["email"] == "updated@example.com"


@pytest.mark.asyncio
async def test_create_product(razorpay_provider):
    """Test product creation."""
    result = await razorpay_provider.create_product(
        name="Premium Plan",
        description="Premium subscription plan",
        meta_info={"features": ["feature1", "feature2"]},
    )
    
    assert result["name"] == "Premium Plan"
    assert result["description"] == "Premium subscription plan"
    assert "provider_product_id" in result


@pytest.mark.asyncio
async def test_create_price_recurring(razorpay_provider):
    """Test recurring price/plan creation."""
    result = await razorpay_provider.create_price(
        product_id="test_product",
        amount=999.0,
        currency="INR",
        interval="month",
        interval_count=1,
        meta_info={"name": "Monthly Plan"},
    )
    
    assert result["amount"] == 999.0
    assert result["currency"] == "INR"
    assert result["interval"] == "month"
    assert result["interval_count"] == 1
    assert "provider_price_id" in result
    assert result["provider_price_id"].startswith("plan_")


@pytest.mark.asyncio
async def test_create_price_onetime(razorpay_provider):
    """Test one-time price creation."""
    result = await razorpay_provider.create_price(
        product_id="test_product",
        amount=500.0,
        currency="INR",
        interval=None,
        meta_info={"name": "One-time Purchase"},
    )
    
    assert result["amount"] == 500.0
    assert result["currency"] == "INR"
    assert result["interval"] is None
    assert "provider_price_id" in result


@pytest.mark.asyncio
async def test_create_subscription(razorpay_provider):
    """Test subscription creation."""
    # First create customer and plan
    customer = await razorpay_provider.create_customer(
        email="test@example.com",
        name="Test Customer",
    )
    
    plan = await razorpay_provider.create_price(
        product_id="test_product",
        amount=999.0,
        currency="INR",
        interval="month",
        interval_count=1,
    )
    
    # Create subscription
    result = await razorpay_provider.create_subscription(
        provider_customer_id=customer["provider_customer_id"],
        price_id=plan["provider_price_id"],
        quantity=1,
        meta_info={"total_count": 12},
    )
    
    assert "provider_subscription_id" in result
    assert result["provider_subscription_id"].startswith("sub_")
    assert result["status"] == "incomplete"  # "created" maps to "incomplete"
    assert result["quantity"] == 1
    assert "short_url" in result["meta_info"]


@pytest.mark.asyncio
async def test_retrieve_subscription(razorpay_provider):
    """Test subscription retrieval."""
    # Create a subscription first
    customer = await razorpay_provider.create_customer(
        email="test@example.com",
        name="Test Customer",
    )
    
    plan = await razorpay_provider.create_price(
        product_id="test_product",
        amount=999.0,
        currency="INR",
        interval="month",
    )
    
    subscription = await razorpay_provider.create_subscription(
        provider_customer_id=customer["provider_customer_id"],
        price_id=plan["provider_price_id"],
    )
    
    # Retrieve it
    result = await razorpay_provider.retrieve_subscription(
        subscription["provider_subscription_id"]
    )
    
    assert result["provider_subscription_id"] == subscription["provider_subscription_id"]


@pytest.mark.asyncio
async def test_update_subscription(razorpay_provider):
    """Test subscription update."""
    # Create a subscription first
    customer = await razorpay_provider.create_customer(
        email="test@example.com",
        name="Test Customer",
    )
    
    plan = await razorpay_provider.create_price(
        product_id="test_product",
        amount=999.0,
        currency="INR",
        interval="month",
    )
    
    subscription = await razorpay_provider.create_subscription(
        provider_customer_id=customer["provider_customer_id"],
        price_id=plan["provider_price_id"],
        quantity=1,
    )
    
    # Update quantity
    result = await razorpay_provider.update_subscription(
        subscription["provider_subscription_id"],
        {"quantity": 2},
    )
    
    assert result["quantity"] == 2


@pytest.mark.asyncio
async def test_cancel_subscription(razorpay_provider):
    """Test subscription cancellation."""
    # Create a subscription first
    customer = await razorpay_provider.create_customer(
        email="test@example.com",
        name="Test Customer",
    )
    
    plan = await razorpay_provider.create_price(
        product_id="test_product",
        amount=999.0,
        currency="INR",
        interval="month",
    )
    
    subscription = await razorpay_provider.create_subscription(
        provider_customer_id=customer["provider_customer_id"],
        price_id=plan["provider_price_id"],
    )
    
    # Cancel at period end
    result = await razorpay_provider.cancel_subscription(
        subscription["provider_subscription_id"],
        cancel_at_period_end=True,
    )
    
    assert result["status"] == "canceled"
    assert result["cancel_at_period_end"] is True


@pytest.mark.asyncio
async def test_cancel_subscription_immediate(razorpay_provider):
    """Test immediate subscription cancellation."""
    customer = await razorpay_provider.create_customer(
        email="test@example.com",
        name="Test Customer",
    )
    
    plan = await razorpay_provider.create_price(
        product_id="test_product",
        amount=999.0,
        currency="INR",
        interval="month",
    )
    
    subscription = await razorpay_provider.create_subscription(
        provider_customer_id=customer["provider_customer_id"],
        price_id=plan["provider_price_id"],
    )
    
    # Cancel immediately
    result = await razorpay_provider.cancel_subscription(
        subscription["provider_subscription_id"],
        cancel_at_period_end=False,
    )
    
    assert result["status"] == "canceled"
    assert result["cancel_at_period_end"] is False


@pytest.mark.asyncio
async def test_pause_subscription(razorpay_provider):
    """Test subscription pause."""
    customer = await razorpay_provider.create_customer(
        email="test@example.com",
        name="Test Customer",
    )
    
    plan = await razorpay_provider.create_price(
        product_id="test_product",
        amount=999.0,
        currency="INR",
        interval="month",
    )
    
    subscription = await razorpay_provider.create_subscription(
        provider_customer_id=customer["provider_customer_id"],
        price_id=plan["provider_price_id"],
    )
    
    # Pause
    result = await razorpay_provider.pause_subscription(
        subscription["provider_subscription_id"]
    )
    
    assert result["status"] == "paused"


@pytest.mark.asyncio
async def test_resume_subscription(razorpay_provider):
    """Test subscription resume."""
    customer = await razorpay_provider.create_customer(
        email="test@example.com",
        name="Test Customer",
    )
    
    plan = await razorpay_provider.create_price(
        product_id="test_product",
        amount=999.0,
        currency="INR",
        interval="month",
    )
    
    subscription = await razorpay_provider.create_subscription(
        provider_customer_id=customer["provider_customer_id"],
        price_id=plan["provider_price_id"],
    )
    
    # Pause first
    await razorpay_provider.pause_subscription(
        subscription["provider_subscription_id"]
    )
    
    # Resume
    result = await razorpay_provider.resume_subscription(
        subscription["provider_subscription_id"]
    )
    
    assert result["status"] == "active"


@pytest.mark.asyncio
async def test_process_payment(razorpay_provider):
    """Test one-time payment processing (order creation)."""
    result = await razorpay_provider.process_payment(
        amount=500.0,
        currency="INR",
        description="Test payment",
        meta_info={"order_item": "test_item"},
    )
    
    assert result["amount"] == 500.0
    assert result["currency"] == "INR"
    assert "provider_payment_id" in result
    assert result["provider_payment_id"].startswith("order_")
    assert result["status"] == "requires_payment_method"


@pytest.mark.asyncio
async def test_refund_payment(razorpay_provider):
    """Test payment refund."""
    # Create a mock payment first
    payment_id = "pay_test123456789"
    
    result = await razorpay_provider.refund_payment(
        provider_payment_id=payment_id,
        amount=100.0,
    )
    
    assert "provider_refund_id" in result
    assert result["provider_refund_id"].startswith("rfnd_")
    assert result["payment_id"] == payment_id
    assert result["status"] == "processed"


@pytest.mark.asyncio
async def test_webhook_handler(razorpay_provider):
    """Test webhook event handling."""
    webhook_payload = {
        "event": "subscription.activated",
        "payload": {
            "subscription": {
                "entity": {
                    "id": "sub_test123",
                    "status": "active",
                }
            }
        }
    }
    
    result = await razorpay_provider.webhook_handler(
        payload=json.dumps(webhook_payload),
        signature="test_signature",
    )
    
    assert result["event_type"] == "subscription.activated"
    assert result["standardized_event_type"] == "subscription.created"
    assert result["provider"] == "razorpay"


@pytest.mark.asyncio
async def test_webhook_handler_payment_captured(razorpay_provider):
    """Test webhook for payment captured event."""
    webhook_payload = {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_test123",
                    "amount": 50000,
                    "currency": "INR",
                    "status": "captured",
                }
            }
        }
    }
    
    result = await razorpay_provider.webhook_handler(
        payload=json.dumps(webhook_payload),
        signature="test_signature",
    )
    
    assert result["event_type"] == "payment.captured"
    assert result["standardized_event_type"] == "payment.succeeded"


@pytest.mark.asyncio
async def test_list_payment_methods(razorpay_provider):
    """Test listing payment methods (tokens)."""
    customer = await razorpay_provider.create_customer(
        email="test@example.com",
        name="Test Customer",
    )
    
    result = await razorpay_provider.list_payment_methods(
        customer["provider_customer_id"]
    )
    
    # Should return empty list for new customer
    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_delete_customer(razorpay_provider):
    """Test customer deletion (local only for Razorpay)."""
    customer = await razorpay_provider.create_customer(
        email="test@example.com",
        name="Test Customer",
    )
    
    result = await razorpay_provider.delete_customer(
        customer["provider_customer_id"]
    )
    
    assert result["deleted"] is True
    assert result["provider_customer_id"] == customer["provider_customer_id"]


@pytest.mark.asyncio
async def test_create_subscription_checkout_config(razorpay_provider):
    """Subscription response includes checkout_config for Razorpay Checkout JS."""
    customer = await razorpay_provider.create_customer(
        email="checkout@example.com",
        name="Checkout User",
        meta_info={"phone": "9999999999"},
    )
    plan = await razorpay_provider.create_price(
        product_id="test_product",
        amount=999.0,
        currency="INR",
        interval="month",
    )
    result = await razorpay_provider.create_subscription(
        provider_customer_id=customer["provider_customer_id"],
        price_id=plan["provider_price_id"],
        meta_info={
            "merchant_name": "Acme Corp",
            "description": "Monthly Plan",
            "email": "checkout@example.com",
            "phone": "9999999999",
            "total_count": 12,
        },
    )

    checkout = result["meta_info"]["checkout_config"]
    assert checkout["key"] == "test_key_id"
    assert checkout["subscription_id"] == result["provider_subscription_id"]
    assert checkout["name"] == "Acme Corp"
    assert checkout["description"] == "Monthly Plan"
    assert checkout["prefill"]["email"] == "checkout@example.com"
    assert checkout["prefill"]["contact"] == "9999999999"


@pytest.mark.asyncio
async def test_process_payment_checkout_config(razorpay_provider):
    """Order response includes checkout_config for Razorpay Checkout JS."""
    result = await razorpay_provider.process_payment(
        amount=500.0,
        currency="INR",
        description="Test purchase",
        meta_info={
            "merchant_name": "My Store",
            "email": "buyer@example.com",
        },
    )

    checkout = result["meta_info"]["checkout_config"]
    assert checkout["key"] == "test_key_id"
    assert checkout["order_id"] == result["provider_payment_id"]
    assert checkout["amount"] == 500 * 100  # paise
    assert checkout["currency"] == "INR"
    assert checkout["name"] == "My Store"
    assert checkout["description"] == "Test purchase"
    assert checkout["prefill"]["email"] == "buyer@example.com"


@pytest.mark.asyncio
async def test_verify_payment_signature_order(razorpay_provider):
    """Verify signature for one-time order checkout."""
    # HMAC-SHA256 of "order_test456|pay_test123" with key "test_key_secret"
    ok = razorpay_provider.verify_payment_signature(
        razorpay_payment_id="pay_test123",
        razorpay_order_id="order_test456",
        razorpay_signature="aec0fd8a1f6525ecdc6f7c2a23bc4e9b05613f2f031904328fada38e64d840b2",
    )
    assert ok is True


@pytest.mark.asyncio
async def test_verify_payment_signature_subscription(razorpay_provider):
    """Verify signature for subscription checkout."""
    # HMAC-SHA256 of \"pay_test123|sub_test456\" with key \"test_key_secret\"
    ok = razorpay_provider.verify_payment_signature(
        razorpay_payment_id="pay_test123",
        razorpay_subscription_id="sub_test456",
        razorpay_signature="4b2e27ba31e664d7000d0710fb9dd4ed21351969e7afc99c365c603d443bb0dd",
    )
    assert ok is True


@pytest.mark.asyncio
async def test_verify_payment_signature_missing_ids(razorpay_provider):
    """verify_payment_signature raises ValueError when neither id is provided."""
    with pytest.raises(ValueError, match="Either razorpay_order_id or razorpay_subscription_id"):
        razorpay_provider.verify_payment_signature(
            razorpay_payment_id="pay_test123",
            razorpay_signature="dummy_sig",
        )


@pytest.mark.asyncio
async def test_amount_conversion(razorpay_provider):
    """Test amount conversion to/from paise."""
    # Test to paise
    assert razorpay_provider._to_razorpay_amount(100.0, "INR") == 10000
    assert razorpay_provider._to_razorpay_amount(99.99, "INR") == 9999
    
    # Test from paise
    assert razorpay_provider._from_razorpay_amount(10000, "INR") == 100.0
    assert razorpay_provider._from_razorpay_amount(9999, "INR") == 99.99


@pytest.mark.asyncio
async def test_interval_mapping(razorpay_provider):
    """Test interval mapping."""
    assert razorpay_provider._map_interval("day") == "daily"
    assert razorpay_provider._map_interval("week") == "weekly"
    assert razorpay_provider._map_interval("month") == "monthly"
    assert razorpay_provider._map_interval("year") == "yearly"


@pytest.mark.asyncio
async def test_status_mapping(razorpay_provider):
    """Test subscription status mapping."""
    assert razorpay_provider._map_subscription_status("created") == "incomplete"
    assert razorpay_provider._map_subscription_status("active") == "active"
    assert razorpay_provider._map_subscription_status("cancelled") == "canceled"
    assert razorpay_provider._map_subscription_status("paused") == "paused"
    assert razorpay_provider._map_subscription_status("halted") == "past_due"
