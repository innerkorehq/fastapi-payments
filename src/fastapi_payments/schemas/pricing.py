from pydantic import BaseModel, Field, validator
from typing import Dict, Any, Optional, List
from datetime import datetime


class TierDefinition(BaseModel):
    """Schema for pricing tier definition."""

    lower_bound: float
    upper_bound: Optional[float] = None
    price_per_unit: float
    flat_fee: float = 0.0
    name: Optional[str] = None


class PriceCalculationRequest(BaseModel):
    """Base schema for price calculation requests."""

    pricing_model: str
    tax_rate: Optional[float] = None

    @validator("pricing_model")
    def validate_pricing_model(cls, v):
        allowed_models = [
            "subscription",
            "usage_based",
            "tiered",
            "per_user",
            "freemium",
            "dynamic",
            "hybrid",
        ]
        if v.lower() not in allowed_models:
            raise ValueError(
                f"Invalid pricing model. Must be one of: {
                    ', '.join(allowed_models)}"
            )
        return v.lower()


class SubscriptionPriceRequest(PriceCalculationRequest):
    """Schema for subscription price calculation."""

    base_amount: float = Field(gt=0)
    quantity: int = 1
    discount_percentage: Optional[float] = Field(None, ge=0, lt=1)
    discount_amount: Optional[float] = Field(None, ge=0)


class UsageBasedPriceRequest(PriceCalculationRequest):
    """Schema for usage-based price calculation."""

    unit_price: float = Field(gt=0)
    usage_quantity: float = Field(gt=0)
    minimum_charge: Optional[float] = Field(None, gt=0)
    maximum_charge: Optional[float] = Field(None, gt=0)
    discount_percentage: Optional[float] = Field(None, ge=0, lt=1)


class TieredPriceRequest(PriceCalculationRequest):
    """Schema for tiered price calculation."""

    tiers: List[TierDefinition]
    quantity: float = Field(gt=0)
    discount_percentage: Optional[float] = Field(None, ge=0, lt=1)


class PriceCalculationResponse(BaseModel):
    """Schema for price calculation response."""

    pricing_model: str
    original_amount: float
    discount_amount: Optional[float] = 0.0
    tax_amount: Optional[float] = 0.0
    final_amount: float
    calculation_breakdown: Optional[Dict[str, Any]] = None


class PlanChangeValidationRequest(BaseModel):
    """Schema for plan change validation."""

    pricing_model: str
    current_plan: Dict[str, Any]
    new_plan: Dict[str, Any]


class PlanChangeValidationResponse(BaseModel):
    """Schema for plan change validation response."""

    allowed: bool
    reason: Optional[str] = None
    proration_amount: Optional[float] = None
