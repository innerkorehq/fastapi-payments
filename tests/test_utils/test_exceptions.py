import pytest

from fastapi_payments.utils.exceptions import (
    PaymentError,
    ProviderError,
    ConfigurationError,
    ValidationError,
    ResourceNotFoundError,
    AuthenticationError,
    WebhookError,
    PaymentRequiresActionError,
)


def test_base_payment_error():
    """Test base PaymentError."""
    error = PaymentError("Payment failed", code="payment_failed")

    assert str(error) == "Payment failed"
    assert error.code == "payment_failed"
    assert error.message == "Payment failed"


def test_provider_error():
    """Test ProviderError with provider-specific details."""
    error = ProviderError(
        message="Provider API error",
        code="api_error",
        provider="stripe",
        provider_error="Invalid API key provided",
    )

    assert str(error) == "Provider API error"
    assert error.code == "api_error"
    assert error.provider == "stripe"
    assert error.provider_error == "Invalid API key provided"


def test_configuration_error():
    """Test ConfigurationError."""
    error = ConfigurationError("Missing required configuration")

    assert str(error) == "Missing required configuration"
    assert isinstance(error, PaymentError)


def test_validation_error():
    """Test ValidationError."""
    error = ValidationError("Invalid card number")

    assert str(error) == "Invalid card number"
    assert isinstance(error, PaymentError)


def test_resource_not_found_error():
    """Test ResourceNotFoundError."""
    error = ResourceNotFoundError("Customer not found")

    assert str(error) == "Customer not found"
    assert isinstance(error, PaymentError)


def test_authentication_error():
    """Test AuthenticationError."""
    error = AuthenticationError("Invalid API key")

    assert str(error) == "Invalid API key"
    assert isinstance(error, PaymentError)


def test_webhook_error():
    """Test WebhookError."""
    error = WebhookError("Invalid webhook signature")

    assert str(error) == "Invalid webhook signature"
    assert isinstance(error, PaymentError)


def test_payment_requires_action_error():
    """Test PaymentRequiresActionError with action details."""
    error = PaymentRequiresActionError(
        message="Payment requires authentication",
        action_url="https://example.com/authenticate",
        action_type="3ds_authentication",
    )

    assert str(error) == "Payment requires authentication"
    assert error.code == "payment_requires_action"
    assert error.action_url == "https://example.com/authenticate"
    assert error.action_type == "3ds_authentication"
    assert isinstance(error, PaymentError)
