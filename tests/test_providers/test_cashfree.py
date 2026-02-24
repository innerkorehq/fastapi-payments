"""Tests for Cashfree payment provider."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from fastapi_payments.config.config_schema import ProviderConfig
from fastapi_payments.providers.cashfree import CashfreeProvider
from tests.fakes.fake_cashfree import FakeCashfree


def _cashfree_pg_mocks():
    """Return a sys.modules patch dict that stubs out the optional cashfree_pg package.

    Covers all submodule paths imported lazily inside CashfreeProvider methods so
    that the tests run without the real cashfree_pg wheel installed.
    """
    mock_cfg_cls = MagicMock(name="Configuration")
    mock_api_cls = MagicMock(name="ApiClient")

    # Build a single models sub-package mock that services attribute lookups for
    # any model class (CreatePlanRequest, CreateOrderRequest, etc.).
    mock_models = MagicMock(name="cashfree_pg.models")

    submodule_names = [
        "cashfree_pg.models.create_plan_request",
        "cashfree_pg.models.create_subscription_request",
        "cashfree_pg.models.subscription_customer_details",
        "cashfree_pg.models.create_order_request",
        "cashfree_pg.models.customer_details",
        "cashfree_pg.models.order_create_refund_request",
    ]

    patches = {
        "cashfree_pg": MagicMock(name="cashfree_pg"),
        "cashfree_pg.configuration": MagicMock(Configuration=mock_cfg_cls),
        "cashfree_pg.api_client": MagicMock(ApiClient=mock_api_cls),
        "cashfree_pg.models": mock_models,
    }
    for sub in submodule_names:
        patches[sub] = MagicMock()

    return patches


@pytest.fixture
def fake_cashfree():
    """Create a fake Cashfree instance."""
    return FakeCashfree()


@pytest.fixture
def cashfree_provider():
    """Create a Cashfree provider instance with mocked cashfree_pg dependency.

    Uses yield so that the sys.modules patch remains active for the duration of
    each test — the provider lazily imports cashfree_pg submodules inside its
    methods, not only at initialisation time.
    """
    config = ProviderConfig(
        api_key="test_client_id",
        api_secret="test_client_secret",
        sandbox_mode=True,
        additional_settings={
            "collection_mode": "india",
            "return_url": "https://merchant.test/return",
            "notify_url": "https://merchant.test/webhook",
        },
    )
    with patch.dict("sys.modules", _cashfree_pg_mocks()):
        yield CashfreeProvider(config)


@pytest.mark.asyncio
async def test_create_customer(cashfree_provider):
    """Test customer creation."""
    result = await cashfree_provider.create_customer(
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
    assert result["provider_customer_id"].startswith("cashfree_")
    assert "address" in result["meta_info"]
    assert result["phone"] == "9999999999"


@pytest.mark.asyncio
async def test_create_product(cashfree_provider):
    """Test product creation."""
    result = await cashfree_provider.create_product(
        name="Premium Plan",
        description="Premium subscription plan",
        meta_info={"features": ["feature1", "feature2"]},
    )
    
    assert result["name"] == "Premium Plan"
    assert result["description"] == "Premium subscription plan"
    assert "provider_product_id" in result
    assert result["provider_product_id"].startswith("cashfree_product_")


@pytest.mark.asyncio
async def test_create_price(cashfree_provider, fake_cashfree):
    """Test price/plan creation."""
    product_id = "cashfree_product_test123"
    
    # Mock the API call
    with patch.object(
        cashfree_provider.api_client, "call_api", new_callable=AsyncMock
    ) as mock_api:
        mock_api.return_value = [fake_cashfree.create_plan({
            "plan_id": "test_price_id",
            "plan_name": "Monthly Plan",
            "plan_type": "PERIODIC",
            "plan_currency": "INR",
            "plan_amount": 99900,
            "plan_interval_type": "MONTHLY",
            "plan_intervals": 1,
        })]
        
        result = await cashfree_provider.create_price(
            product_id=product_id,
            amount=999.0,
            currency="INR",
            interval="month",
            interval_count=1,
            meta_info={"name": "Monthly Plan"},
        )
        
        assert result["product_id"] == product_id
        assert result["amount"] == 999.0
        assert result["currency"] == "INR"
        assert result["interval"] == "month"
        assert "provider_price_id" in result


@pytest.mark.asyncio
async def test_create_subscription(cashfree_provider, fake_cashfree):
    """Test subscription creation."""
    customer_id = "cashfree_cust_test123"
    price_id = "cashfree_price_test456"
    
    # Mock the API call
    with patch.object(
        cashfree_provider.api_client, "call_api", new_callable=AsyncMock
    ) as mock_api:
        subscription_response = fake_cashfree.create_subscription({
            "subscription_id": "sub_test_123",
            "plan_id": price_id,
            "subscription_customer_details": {
                "customer_id": customer_id,
                "customer_name": "Test Customer",
                "customer_email": "test@example.com",
                "customer_phone": "9999999999",
            },
        })
        mock_api.return_value = [subscription_response]
        
        result = await cashfree_provider.create_subscription(
            provider_customer_id=customer_id,
            price_id=price_id,
            quantity=1,
            meta_info={
                "customer_name": "Test Customer",
                "customer_email": "test@example.com",
                "customer_phone": "9999999999",
            },
        )
        
        assert result["provider_customer_id"] == customer_id
        assert result["price_id"] == price_id
        assert result["status"] == "pending"  # INITIALIZED maps to pending
        assert "authorization_url" in result["meta_info"]


@pytest.mark.asyncio
async def test_create_subscription_requires_customer_details(cashfree_provider):
    """Test that subscription creation requires customer details."""
    with pytest.raises(ValueError, match="Customer name and email are required for Cashfree subscriptions"):
        await cashfree_provider.create_subscription(
            provider_customer_id="cust_123",
            price_id="price_456",
            meta_info={},
        )


@pytest.mark.asyncio
async def test_process_payment(cashfree_provider, fake_cashfree):
    """Test payment processing."""
    customer_id = "cashfree_cust_test123"
    
    # Mock the API call
    with patch.object(
        cashfree_provider.api_client, "call_api", new_callable=AsyncMock
    ) as mock_api:
        order_response = fake_cashfree.create_order({
            "order_id": "order_test_123",
            "order_amount": 100.0,
            "order_currency": "INR",
            "customer_details": {
                "customer_id": customer_id,
                "customer_name": "Test Customer",
                "customer_email": "test@example.com",
                "customer_phone": "9999999999",
            },
        })
        mock_api.return_value = [order_response]
        
        result = await cashfree_provider.process_payment(
            amount=100.0,
            currency="INR",
            provider_customer_id=customer_id,
            description="Test payment",
            meta_info={
                "cashfree": {
                    "customer_name": "Test Customer",
                    "customer_email": "test@example.com",
                    "customer_phone": "9999999999",
                },
            },
        )
        
        assert result["amount"] == 100.0
        assert result["currency"] == "INR"
        assert result["status"] == "pending"
        assert result["provider_customer_id"] == customer_id
        assert "payment_session_id" in result["meta_info"]
        assert "order_token" in result["meta_info"]


@pytest.mark.asyncio
async def test_process_payment_requires_customer_details(cashfree_provider):
    """Test that payment processing requires customer details."""
    with pytest.raises(ValueError, match="Customer name and email are required"):
        await cashfree_provider.process_payment(
            amount=100.0,
            currency="INR",
            provider_customer_id="cust_123",
            meta_info={},
        )


@pytest.mark.asyncio
async def test_refund_payment(cashfree_provider, fake_cashfree):
    """Test payment refund."""
    payment_id = "cashfree_payment_test123"
    order_id = "order_test_123"
    
    # Create fake order first
    fake_cashfree.create_order({
        "order_id": order_id,
        "order_amount": 100.0,
        "order_currency": "INR",
        "customer_details": {
            "customer_id": "cust_123",
            "customer_name": "Test",
            "customer_email": "test@example.com",
            "customer_phone": "9999999999",
        },
    })
    
    # Mock the API call
    with patch.object(
        cashfree_provider.api_client, "call_api", new_callable=AsyncMock
    ) as mock_api:
        refund_response = fake_cashfree.create_refund(order_id, {
            "refund_id": "refund_test_123",
            "refund_amount": 50.0,
            "refund_note": "Customer request",
        })
        mock_api.return_value = [refund_response]
        
        result = await cashfree_provider.refund_payment(
            provider_payment_id=payment_id,
            amount=50.0,
            meta_info={
                "cashfree": {
                    "order_id": order_id,
                    "refund_note": "Customer request",
                }
            },
        )
        
        assert result["amount"] == 50.0
        assert result["status"] == "succeeded"
        assert "provider_refund_id" in result


@pytest.mark.asyncio
async def test_refund_payment_requires_order_id(cashfree_provider):
    """Test that refund requires order_id."""
    with pytest.raises(ValueError, match="order_id is required"):
        await cashfree_provider.refund_payment(
            provider_payment_id="payment_123",
            amount=50.0,
            meta_info={},
        )


@pytest.mark.asyncio
async def test_retrieve_subscription(cashfree_provider, fake_cashfree):
    """Test subscription retrieval."""
    subscription_id = "sub_test_123"
    
    # Create fake subscription
    fake_cashfree.create_subscription({
        "subscription_id": subscription_id,
        "plan_id": "plan_123",
        "subscription_customer_details": {
            "customer_id": "cust_123",
            "customer_name": "Test",
            "customer_email": "test@example.com",
            "customer_phone": "9999999999",
        },
    })
    
    # Mock the API call
    with patch.object(
        cashfree_provider.api_client, "call_api", new_callable=AsyncMock
    ) as mock_api:
        mock_api.return_value = [fake_cashfree.get_subscription(subscription_id)]
        
        result = await cashfree_provider.retrieve_subscription(subscription_id)
        
        assert result["provider_subscription_id"] == subscription_id
        assert result["status"] == "pending"  # INITIALIZED maps to pending


@pytest.mark.asyncio
async def test_cancel_subscription(cashfree_provider, fake_cashfree):
    """Test subscription cancellation."""
    subscription_id = "sub_test_123"
    
    # Create fake subscription
    fake_cashfree.create_subscription({
        "subscription_id": subscription_id,
        "plan_id": "plan_123",
        "subscription_customer_details": {
            "customer_id": "cust_123",
            "customer_name": "Test",
            "customer_email": "test@example.com",
            "customer_phone": "9999999999",
        },
    })
    
    # Mock the API call
    with patch.object(
        cashfree_provider.api_client, "call_api", new_callable=AsyncMock
    ) as mock_api:
        mock_api.return_value = [fake_cashfree.cancel_subscription(subscription_id)]
        
        result = await cashfree_provider.cancel_subscription(subscription_id)
        
        assert result["provider_subscription_id"] == subscription_id
        assert result["status"] == "canceled"


@pytest.mark.asyncio
async def test_webhook_handler_payment_success(cashfree_provider, fake_cashfree):
    """Test webhook handling for payment success."""
    webhook_payload = fake_cashfree.simulate_webhook(
        "PAYMENT_SUCCESS_WEBHOOK",
        {
            "order": {
                "order_id": "order_test_123",
                "order_amount": 100.0,
            },
            "payment": {
                "cf_payment_id": "payment_123",
                "payment_status": "SUCCESS",
            },
        },
    )
    
    result = await cashfree_provider.webhook_handler(webhook_payload)
    
    assert result["event_type"] == "PAYMENT_SUCCESS_WEBHOOK"
    assert result["standardized_event_type"] == "payment.succeeded"
    assert "event_id" in result
    assert "timestamp" in result


@pytest.mark.asyncio
async def test_webhook_handler_subscription_activated(cashfree_provider, fake_cashfree):
    """Test webhook handling for subscription activation."""
    webhook_payload = fake_cashfree.simulate_webhook(
        "SUBSCRIPTION_ACTIVATED",
        {
            "subscription": {
                "subscription_id": "sub_test_123",
                "status": "ACTIVE",
            }
        },
    )
    
    result = await cashfree_provider.webhook_handler(webhook_payload)
    
    assert result["event_type"] == "SUBSCRIPTION_ACTIVATED"
    assert result["standardized_event_type"] == "subscription.created"


@pytest.mark.asyncio
async def test_webhook_handler_requires_type(cashfree_provider):
    """Test that webhook handler requires event type."""
    with pytest.raises(ValueError, match="missing 'type' field"):
        await cashfree_provider.webhook_handler({})


def test_verify_webhook_signature(cashfree_provider):
    """Test webhook signature verification."""
    import hmac
    import hashlib
    
    timestamp = "1234567890"
    payload = '{"type":"PAYMENT_SUCCESS_WEBHOOK","data":{}}'
    
    # Create expected signature
    signature_data = f"{timestamp}{payload}"
    expected_signature = hmac.new(
        cashfree_provider.client_secret.encode("utf-8"),
        signature_data.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    
    # Verify
    assert cashfree_provider._verify_webhook_signature(
        payload, expected_signature, timestamp
    )
    
    # Test with wrong signature
    assert not cashfree_provider._verify_webhook_signature(
        payload, "wrong_signature", timestamp
    )


def test_global_collection_mode():
    """Test that global collection mode is properly configured."""
    config = ProviderConfig(
        api_key="test_client_id",
        api_secret="test_client_secret",
        sandbox_mode=True,
        additional_settings={
            "collection_mode": "global",
        },
    )
    with patch.dict("sys.modules", _cashfree_pg_mocks()):
        provider = CashfreeProvider(config)

    assert provider.collection_mode == "global"
    assert "sandbox.cashfree.com" in provider.configuration.host


def test_india_collection_mode():
    """Test that India collection mode is default."""
    config = ProviderConfig(
        api_key="test_client_id",
        api_secret="test_client_secret",
        sandbox_mode=True,
    )
    with patch.dict("sys.modules", _cashfree_pg_mocks()):
        provider = CashfreeProvider(config)

    assert provider.collection_mode == "india"
