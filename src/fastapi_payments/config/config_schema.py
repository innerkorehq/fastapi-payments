from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field, field_validator


class TaxConfig(BaseModel):
    """Tax configuration."""

    default_rate: float = 0.0
    included_in_price: bool = False
    use_tax_service: bool = False
    tax_service_url: Optional[str] = None


class PricingConfig(BaseModel):
    """Pricing configuration."""

    default_currency: str = "USD"
    default_pricing_model: str = "subscription"
    round_to_decimal_places: int = 2
    allow_custom_pricing: bool = True
    tax: TaxConfig = TaxConfig()
    additional_settings: Dict[str, Any] = Field(default_factory=dict)


class DatabaseConfig(BaseModel):
    """Database configuration."""

    url: str
    echo: bool = False
    pool_size: int = 5
    max_overflow: int = 10


class MessagingConfig(BaseModel):
    """Configuration for messaging system."""

    broker_type: str = "redis"
    url: Optional[str] = None
    exchange_name: Optional[str] = None
    queue_prefix: Optional[str] = "payment_"
    topic_prefix: Optional[str] = "payments."
    group_id: Optional[str] = "payment-service"

    @field_validator("broker_type")
    @classmethod
    def validate_broker_type(cls, v):
        """Validate broker type."""
        allowed_types = ["redis", "rabbitmq", "kafka", "nats", "memory"]
        if v not in allowed_types:
            raise ValueError(f"broker_type must be one of {allowed_types}")
        return v


class ProviderConfig(BaseModel):
    """Payment provider configuration."""

    api_key: str
    api_secret: Optional[str] = None
    webhook_secret: Optional[str] = None
    sandbox_mode: bool = True
    additional_settings: Dict[str, Any] = Field(default_factory=dict)


class PaymentConfig(BaseModel):
    """Configuration for payment module."""

    providers: Dict[str, Any]
    database: DatabaseConfig
    messaging: MessagingConfig = Field(default_factory=MessagingConfig)
    pricing: PricingConfig = PricingConfig()
    default_provider: str = "stripe"
    retry_attempts: int = 3
    retry_delay: int = 5
    logging_level: str = "INFO"
    debug: bool = False
    allowed_currencies: List[str] = ["USD", "EUR", "GBP"]
    additional_settings: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("default_provider")
    @classmethod
    def validate_default_provider(cls, v, info):
        """Validate default provider exists in providers."""
        if v not in info.data.get("providers", {}):
            raise ValueError(f"default_provider '{v}' must exist in providers")
        return v

    @field_validator("logging_level")
    @classmethod
    def validate_logging_level(cls, v):
        """Validate logging level."""
        allowed_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v not in allowed_levels:
            raise ValueError(f"logging_level must be one of {allowed_levels}")
        return v
