import pytest
from pydantic import ValidationError

from fastapi_payments.config.config_schema import PaymentConfig


def test_config_validation():
    """Test configuration validation."""
    # Missing required fields
    with pytest.raises(ValidationError):
        PaymentConfig()

    # Invalid provider
    with pytest.raises(ValidationError):
        PaymentConfig(
            providers={
                "stripe": {
                    "api_key": "test_key",
                    "webhook_secret": "test_secret",
                    "sandbox_mode": True,
                }
            },
            database={"url": "sqlite:///:memory:"},
            messaging={
                "broker_type": "memory",
                "url": "memory://",
            },
            default_provider="nonexistent_provider",
        )

    # Invalid logging level
    with pytest.raises(ValidationError):
        PaymentConfig(
            providers={
                "stripe": {
                    "api_key": "test_key",
                    "webhook_secret": "test_secret",
                    "sandbox_mode": True,
                }
            },
            database={"url": "sqlite:///:memory:"},
            messaging={
                "broker_type": "memory",
                "url": "memory://",
            },
            default_provider="stripe",
            logging_level="INVALID",
        )

    # Valid configuration
    config = PaymentConfig(
        providers={
            "stripe": {
                "api_key": "test_key",
                "webhook_secret": "test_secret",
                "sandbox_mode": True,
            }
        },
        database={"url": "sqlite:///:memory:"},
        messaging={
            "broker_type": "memory",
            "url": "memory://",
        },
        default_provider="stripe",
        logging_level="INFO",
    )

    assert config.default_provider == "stripe"
    assert config.logging_level == "INFO"
