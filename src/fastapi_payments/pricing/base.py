from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from ..config.config_schema import PricingConfig


class PricingStrategy(ABC):
    """Abstract base class for pricing strategies."""

    def __init__(self, config: PricingConfig):
        self.config = config

    @abstractmethod
    async def calculate_price(self, **kwargs) -> float:
        """Calculate price based on the pricing model."""
        pass

    @abstractmethod
    async def calculate_proration(
        self,
        previous_plan: Dict[str, Any],
        new_plan: Dict[str, Any],
        days_used: int,
        days_in_period: int,
    ) -> float:
        """Calculate the prorated amount for plan changes."""
        pass

    @abstractmethod
    async def get_billing_items(self, **kwargs) -> List[Dict[str, Any]]:
        """Get items for a bill/invoice."""
        pass

    @abstractmethod
    async def validate_plan_change(
        self, current_plan: Dict[str, Any], new_plan: Dict[str, Any]
    ) -> bool:
        """Validate if a plan change is allowed."""
        pass

    def round_price(self, amount: float) -> float:
        """Round the price according to configuration."""
        return round(amount, self.config.round_to_decimal_places)

    def apply_tax(self, amount: float, tax_rate: Optional[float] = None) -> float:
        """Apply tax to the amount."""
        if tax_rate is None:
            tax_rate = self.config.tax.default_rate

        if self.config.tax.included_in_price:
            # Tax is already included in the price
            return amount
        else:
            # Add tax to the price
            return self.round_price(amount * (1 + tax_rate))

    def calculate_tax_amount(
        self, amount: float, tax_rate: Optional[float] = None
    ) -> float:
        """Calculate the tax amount."""
        if tax_rate is None:
            tax_rate = self.config.tax.default_rate

        if self.config.tax.included_in_price:
            # Calculate tax amount included in the price
            return self.round_price(amount - (amount / (1 + tax_rate)))
        else:
            # Calculate tax amount to be added
            return self.round_price(amount * tax_rate)
