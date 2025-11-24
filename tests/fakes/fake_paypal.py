import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock


class FakePayPal:
    """A small hermetic in-memory PayPal-like provider for tests.

    This mirrors the minimal behavior used by tests in
    tests/test_providers/test_paypal.py so tests can reuse the helper.
    """

    def __init__(self):
        # Attributes commonly set on the real provider
        self.token_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        self.webhook_secret = "test_webhook_secret"
        self.client = MagicMock()
        self.http_client = AsyncMock()
        self.access_token = "test_access_token"

    async def create_customer(self, *args, **kwargs):
        return {
            "provider_customer_id": "CUSTOMER-ID-1234",
            "email": kwargs.get("email", "test@example.com"),
            "name": kwargs.get("name"),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "meta_info": kwargs.get("meta_info", {}),
        }

    async def create_product(self, *args, **kwargs):
        return {
            "provider_product_id": "PROD-1234",
            "name": kwargs.get("name", "Test Product"),
            "description": kwargs.get("description", "A test product"),
            "active": True,
            "meta_info": kwargs.get("meta_info", {}),
        }

    async def create_price(self, *args, **kwargs):
        return {
            "provider_price_id": "PLAN-1234",
            "product_id": kwargs.get("product_id", "PROD-1234"),
            "amount": kwargs.get("amount", 19.99),
            "currency": kwargs.get("currency", "USD"),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "meta_info": kwargs.get("meta_info", {}),
        }

    async def create_subscription(self, *args, **kwargs):
        now = datetime.now(timezone.utc)
        return {
            "provider_subscription_id": "SUB-1234",
            "customer_id": kwargs.get("provider_customer_id", "CUSTOMER-ID-1234"),
            "status": "active",
            "current_period_start": now.isoformat(),
            "current_period_end": (now + timedelta(days=30)).isoformat(),
            "cancel_at_period_end": False,
            "meta_info": kwargs.get("meta_info", {}),
        }

    async def process_payment(self, *args, **kwargs):
        return {
            "provider_payment_id": "PAY-1234",
            "amount": kwargs.get("amount", 10.00),
            "currency": kwargs.get("currency", "USD"),
            "status": "COMPLETED",
            "payment_method": kwargs.get("payment_method_id"),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "meta_info": kwargs.get("meta_info", {}),
        }

    async def webhook_handler(self, *args, **kwargs):
        payload = kwargs.get("payload", {})
        return {
            "event_type": payload.get("event_type", "PAYMENT.CAPTURE.COMPLETED"),
            "standardized_event_type": "payment.succeeded",
            "data": {
                "id": payload.get("resource", {}).get("id", "5O190127TN364715T"),
                "status": payload.get("resource", {}).get("status", "COMPLETED"),
            },
        }


@pytest.fixture
def paypal_provider():
    """Pytest fixture wrapper that returns a fresh FakePayPal instance.

    Note: tests that need to mock webhook verification or tweak state can
    still patch attributes on the returned object.
    """
    return FakePayPal()
