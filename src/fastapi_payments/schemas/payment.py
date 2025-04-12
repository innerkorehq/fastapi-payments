from pydantic import BaseModel, Field, EmailStr, field_validator
from typing import Dict, Any, Optional, List
from datetime import datetime


class CustomerCreate(BaseModel):
    """Schema for creating a customer."""

    email: EmailStr
    name: Optional[str] = None
    meta_info: Optional[Dict[str, Any]] = None


class CustomerResponse(BaseModel):
    """Schema for customer response."""

    id: str
    email: str
    name: Optional[str] = None
    meta_info: Optional[Dict[str, Any]] = None
    created_at: str
    provider_customer_id: Optional[str] = None
    provider_customers: Optional[List[Dict[str, Any]]] = None


class PaymentMethodCreate(BaseModel):
    """Schema for creating a payment method."""

    type: str
    card: Optional[Dict[str, Any]] = None
    token: Optional[str] = None
    set_default: bool = False


class PaymentMethodResponse(BaseModel):
    """Schema for payment method response."""

    id: str
    provider: str
    type: str
    is_default: bool = False
    card: Optional[Dict[str, Any]] = None


class ProductCreate(BaseModel):
    """Schema for creating a product."""

    name: str
    description: Optional[str] = None
    meta_info: Optional[Dict[str, Any]] = None


class ProductResponse(BaseModel):
    """Schema for product response."""

    id: str
    name: str
    description: Optional[str] = None
    active: bool
    provider_product_id: str
    provider: str
    created_at: str
    meta_info: Optional[Dict[str, Any]] = None


class PlanCreate(BaseModel):
    """Schema for creating a plan."""

    name: str
    pricing_model: str = "subscription"
    description: Optional[str] = None
    amount: float
    currency: str = "USD"
    billing_interval: Optional[str] = None
    billing_interval_count: Optional[int] = 1
    trial_period_days: Optional[int] = None
    meta_info: Optional[Dict[str, Any]] = None

    @field_validator("pricing_model")
    @classmethod
    def validate_pricing_model(cls, v):
        """Validate pricing model."""
        allowed_models = [
            "subscription",
            "usage_based",
            "tiered",
            "per_user",
            "freemium",
            "dynamic",
            "hybrid",
        ]
        if v not in allowed_models:
            raise ValueError(f"pricing_model must be one of {allowed_models}")
        return v


class PlanResponse(BaseModel):
    """Schema for plan response."""

    id: str
    product_id: str
    name: str
    description: Optional[str] = None
    pricing_model: str
    amount: float
    currency: str
    billing_interval: Optional[str] = None
    billing_interval_count: Optional[int] = None
    trial_period_days: Optional[int] = None
    provider: str
    provider_price_id: str
    created_at: str


class SubscriptionCreate(BaseModel):
    """Schema for creating a subscription."""

    plan_id: str
    quantity: int = 1
    trial_period_days: Optional[int] = None
    meta_info: Optional[Dict[str, Any]] = None


class SubscriptionResponse(BaseModel):
    """Schema for subscription response."""

    id: str
    customer_id: str
    plan_id: str
    plan_name: Optional[str] = None
    provider: str
    provider_subscription_id: str
    status: str
    quantity: int
    current_period_start: str
    current_period_end: Optional[str] = None
    cancel_at_period_end: bool
    created_at: str
    provider_data: Optional[Dict[str, Any]] = None


class PaymentCreate(BaseModel):
    """Schema for creating a payment."""

    customer_id: str
    amount: float = Field(gt=0)
    currency: str = "USD"
    payment_method_id: Optional[str] = None
    description: Optional[str] = None
    meta_info: Optional[Dict[str, Any]] = None


class PaymentResponse(BaseModel):
    """Schema for payment response."""

    id: str
    customer_id: str
    amount: float
    refunded_amount: Optional[float] = 0.0
    currency: str
    status: str
    payment_method: Optional[str] = None
    error_message: Optional[str] = None
    provider: str
    provider_payment_id: str
    created_at: str
