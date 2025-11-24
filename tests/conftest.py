import asyncio
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from fastapi_payments import FastAPIPayments
from fastapi_payments.config.config_schema import PaymentConfig, DatabaseConfig
from fastapi_payments.messaging.publishers import PaymentEventPublisher
from fastapi_payments.services.payment_service import PaymentService
from fastapi_payments.api.dependencies import (
    initialize_dependencies,
    get_payment_service,
    get_config,
)
from fastapi_payments.db.repositories import initialize_db

# Paths
_REPO_ROOT = Path(__file__).resolve().parents[1]
_TEST_DB_PATH = _REPO_ROOT / "test_payments.db"


# Test configuration
TEST_CONFIG = {
    "providers": {
        "stripe": {
            "api_key": "sk_test_mock_key",
            "webhook_secret": "whsec_mock_secret",
            "sandbox_mode": True,
        }
    },
    "database": {
        "url": f"sqlite+aiosqlite:///{_TEST_DB_PATH.as_posix()}",
        "echo": False,
    },
    "messaging": {
        "broker_type": "memory",
        "url": "memory://",
        "exchange_name": "test_exchange",
        "queue_prefix": "test_",
    },
    "default_provider": "stripe",
}


@pytest.fixture(scope="session", autouse=True)
def initialize_test_dependencies():
    """Initialize dependencies for testing - runs once at the start of test session."""
    config = PaymentConfig(**TEST_CONFIG)
    initialize_dependencies(config)

    # Replace the real stripe SDK with our local FakeStripe for tests so
    # integration tests remain hermetic and don't hit the network.
    try:
        # import the shared FakeStripe used in provider unit tests
        from tests.fakes.fake_stripe import FakeStripe

        # also import optional fakes for other providers
        try:
            from tests.fakes.fake_payu import FakePayU
        except Exception:
            FakePayU = None

        # dependencies._payment_service is created by initialize_dependencies
        from fastapi_payments.api import dependencies as deps

        if getattr(deps, "_payment_service", None):
            # Replace internals for Stripe provider so unit and integration tests
            # don't make network calls.
            provider = deps._payment_service.providers.get("stripe")
            if provider:
                provider._run_stripe_calls_in_thread = False
                provider.stripe = FakeStripe()
                provider.stripe_error = provider.stripe.error

            # If the app initialized a PayU provider, replace it with our fake
            # PayU implementation so hosted-checkout integration tests are hermetic.
            if FakePayU:
                payu_provider = deps._payment_service.providers.get("payu")
                if payu_provider:
                    deps._payment_service.providers["payu"] = FakePayU()
    except Exception:
        # If any of the imports fail (test module missing etc.) just continue
        # — tests that rely on real stripe will fail but we don't want to
        # abort test session initialization.
        pass

    # Initialize database
    if _TEST_DB_PATH.exists():
        _TEST_DB_PATH.unlink()
    db_config = DatabaseConfig(**TEST_CONFIG["database"])
    initialize_db(db_config)

    return config
    


@pytest.fixture
def event_loop_policy():
    """Return the event loop policy to use."""
    return asyncio.get_event_loop_policy()


@pytest.fixture
def mock_event_publisher():
    """Create a mock event publisher that stores events."""

    class MockEventPublisher:
        def __init__(self):
            self.events = []
            # Create a mock config with minimum required attributes
            self.config = type(
                "MockConfig",
                (),
                {
                    "broker_type": "memory",
                    "url": "memory://",
                    "exchange_name": "test_exchange",
                },
            )

        async def publish_event(self, event_type, data, routing_key=None):
            self.events.append(
                {
                    "event_type": event_type,
                    "data": data,
                    "routing_key": routing_key,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )

        async def start(self):
            pass

        async def stop(self):
            pass

    return MockEventPublisher()


@pytest.fixture
def test_config():
    """Get test configuration."""
    return PaymentConfig(**TEST_CONFIG)


@pytest.fixture
def mock_payment_service(mock_event_publisher):
    """Create a mock payment service with a mock event publisher."""
    service = PaymentService(
        PaymentConfig(**TEST_CONFIG),
        mock_event_publisher,
        None,  # No DB session for this mock
    )
    return service


@pytest.fixture
def test_app(initialize_test_dependencies):
    """Create a test FastAPI application with payment routes."""
    from fastapi import FastAPI
    from fastapi_payments import FastAPIPayments

    app = FastAPI()

    # Initialize payments module
    payments = FastAPIPayments(TEST_CONFIG)
    payments.include_router(app)

    return app


@pytest.fixture
def async_client_factory(test_app):
    """Get an async HTTP client factory."""

    def _create_client():
        return AsyncClient(app=test_app, base_url="http://test")

    return _create_client


@pytest.fixture
async def async_client(async_client_factory):
    """Get an async HTTP client."""
    client = async_client_factory()
    try:
        yield client
    finally:
        await client.aclose()


@pytest.fixture
def integration_config():
    """Get integration test configuration."""
    return TEST_CONFIG.copy()
