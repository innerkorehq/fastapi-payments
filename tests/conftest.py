import pytest
from fastapi import FastAPI
from httpx import AsyncClient
import asyncio
from datetime import datetime, timezone

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

# Test configuration
TEST_CONFIG = {
    "providers": {
        "stripe": {
            "api_key": "sk_test_mock_key",
            "webhook_secret": "whsec_mock_secret",
            "sandbox_mode": True,
        }
    },
    "database": {"url": "sqlite+aiosqlite:///:memory:", "echo": True},
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

    # Initialize database
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
