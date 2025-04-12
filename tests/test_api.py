import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import AsyncClient
import json
from datetime import datetime, timezone

from fastapi_payments.api.routes import router
from fastapi_payments.services.payment_service import PaymentService
from fastapi_payments.db.repositories import initialize_db
from fastapi_payments.config.config_schema import DatabaseConfig
from fastapi_payments.api.dependencies import get_payment_service_with_db


@pytest.fixture
def mock_payment_service():
    """Create a mock payment service with database checks disabled."""
    service = AsyncMock(spec=PaymentService)

    # Set up mock results that match the response models
    # Use timezone-aware datetime
    created_at = datetime.now(timezone.utc).isoformat()

    # CustomerResponse schema
    service.create_customer.return_value = {
        "id": "cust_123",
        "email": "test@example.com",
        "name": "Test User",
        "created_at": created_at,
        "meta_info": {"source": "api"},
    }

    # CustomerResponse schema
    service.get_customer.return_value = {
        "id": "cust_123",
        "email": "test@example.com",
        "name": "Test User",
        "created_at": created_at,
        "provider_customers": [
            {"provider": "stripe", "provider_customer_id": "cus_test_123"}
        ],
    }

    # PaymentMethodResponse schema
    service.create_payment_method.return_value = {
        "id": "pm_123",
        "type": "card",
        "provider": "stripe",
        "card": {"brand": "visa", "last4": "4242", "exp_month": 12, "exp_year": 2030},
        "is_default": True,
        "created_at": created_at,
    }

    # SubscriptionResponse schema
    service.create_subscription.return_value = {
        "id": "sub_123",
        "customer_id": "cust_123",
        "plan_id": "plan_123",
        "provider": "stripe",
        "provider_subscription_id": "sub_test_123",
        "status": "active",
        "quantity": 1,
        "current_period_start": created_at,
        "current_period_end": created_at,
        "cancel_at_period_end": False,
        "created_at": created_at,
    }

    # PaymentResponse schema
    service.process_payment.return_value = {
        "id": "pay_123",
        "customer_id": "cust_123",
        "amount": 19.99,
        "currency": "USD",
        "status": "COMPLETED",
        "payment_method": "pm_123",
        "provider": "stripe",
        "provider_payment_id": "pi_test_123",
        "created_at": created_at,
    }

    service.handle_webhook.return_value = {"event_type": "payment.succeeded"}

    # Bypass database checks
    service.db_session = "mocked_session"  # Just need something non-None
    service.set_db_session.return_value = None

    # Override the properties that check for database
    service.customer_repo = MagicMock()
    service.payment_repo = MagicMock()
    service.subscription_repo = MagicMock()
    service.product_repo = MagicMock()
    service.plan_repo = MagicMock()

    return service


@pytest.fixture
def test_app(mock_payment_service):
    """Create a FastAPI test app with mocked dependencies."""
    app = FastAPI()

    # Add the payment routes
    app.include_router(router, prefix="/payments")

    # Important: Mock the exact path of the dependency being used
    # The string here must match exactly how it's imported in routes.py
    app.dependency_overrides[get_payment_service_with_db] = lambda: mock_payment_service

    return app


@pytest.fixture
def client(test_app):
    """Create a test client."""
    return TestClient(test_app)


def test_create_customer(client, mock_payment_service):
    """Test creating a customer."""
    response = client.post(
        "/payments/customers",
        json={
            "email": "test@example.com",
            "name": "Test User",
            "meta_info": {"source": "api"},
        },
    )

    assert response.status_code == 200
    assert response.json()["id"] == "cust_123"
    assert response.json()["email"] == "test@example.com"
    mock_payment_service.create_customer.assert_called_once()


def test_get_customer(client, mock_payment_service):
    """Test getting a customer."""
    response = client.get("/payments/customers/cust_123")

    assert response.status_code == 200
    assert response.json()["id"] == "cust_123"
    assert response.json()["email"] == "test@example.com"
    mock_payment_service.get_customer.assert_called_once()


def test_create_payment_method(client, mock_payment_service):
    """Test creating a payment method."""
    response = client.post(
        "/payments/customers/cust_123/payment-methods",
        json={
            "type": "card",
            "card": {
                "number": "4242424242424242",
                "exp_month": 12,
                "exp_year": 2030,
                "cvc": "123",
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["id"] == "pm_123"
    mock_payment_service.create_payment_method.assert_called_once()


def test_create_subscription(client, mock_payment_service):
    """Test creating a subscription."""
    response = client.post(
        "/payments/customers/cust_123/subscriptions",
        json={"plan_id": "plan_123", "quantity": 1},
    )

    assert response.status_code == 200
    assert response.json()["id"] == "sub_123"
    assert response.json()["status"] == "active"
    mock_payment_service.create_subscription.assert_called_once()


def test_process_payment(client, mock_payment_service):
    """Test processing a payment."""
    response = client.post(
        "/payments/payments",
        json={
            "customer_id": "cust_123",
            "amount": 19.99,
            "currency": "USD",
            "payment_method_id": "pm_123",
            "description": "Test payment",
        },
    )

    assert response.status_code == 200
    assert response.json()["id"] == "pay_123"
    mock_payment_service.process_payment.assert_called_once()


def test_webhook_handler(client, mock_payment_service):
    """Test handling a webhook."""
    response = client.post(
        "/payments/webhooks/stripe",
        headers={"Stripe-Signature": "test_signature"},
        json={
            "event_type": "payment_intent.succeeded",
            "data": {"object": {"id": "pi_123"}},
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "success"
    mock_payment_service.handle_webhook.assert_called_once()
