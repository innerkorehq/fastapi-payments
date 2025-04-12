"""Dynamic pricing model implementation."""

from .base import PricingStrategy
from typing import Dict, Any, Optional, List


class DynamicPricing(PricingStrategy):
    """Dynamic pricing strategy based on variable multipliers."""

    def __init__(self, base_price, default_multiplier=1.0, tax_rate=0.0):
        """
        Initialize the dynamic pricing strategy.

        Args:
            base_price: Base price
            default_multiplier: Default price multiplier to apply
            tax_rate: Tax rate
        """
        self.base_price = base_price
        self.default_multiplier = default_multiplier
        self.tax_rate = tax_rate

    def calculate_price(self, custom_multiplier=None, tax_rate=None):
        """
        Calculate price using dynamic pricing.

        Args:
            custom_multiplier: Override default multiplier (optional)
            tax_rate: Override default tax rate (optional)

        Returns:
            Calculated total price
        """
        multiplier = (
            custom_multiplier
            if custom_multiplier is not None
            else self.default_multiplier
        )
        tax_rate = tax_rate if tax_rate is not None else self.tax_rate

        price = self.base_price * multiplier
        tax_amount = price * tax_rate
        return price + tax_amount

    def get_billing_items(self, custom_multiplier=None):
        """
        Get itemized billing details.

        Args:
            custom_multiplier: Override default multiplier (optional)

        Returns:
            List of billing items
        """
        multiplier = (
            custom_multiplier
            if custom_multiplier is not None
            else self.default_multiplier
        )
        price = self.base_price * multiplier

        items = [
            {
                "description": "Base price",
                "quantity": 1,
                "unit_price": self.base_price,
                "amount": self.base_price,
            }
        ]

        # Add multiplier adjustment if not 1.0
        if multiplier != 1.0:
            multiplier_adjustment = self.base_price * (multiplier - 1.0)
            items.append(
                {
                    "description": f"Price multiplier ({multiplier}x)",
                    "quantity": 1,
                    "unit_price": multiplier_adjustment,
                    "amount": multiplier_adjustment,
                }
            )

        return items

    def calculate_proration(
        self, days_used: int, days_in_period: int, quantity: int = 1
    ) -> float:
        """
        Calculate prorated price amount.

        Args:
            days_used: Days used in period
            days_in_period: Total days in period
            quantity: Quantity (not typically used in dynamic pricing)

        Returns:
            Prorated price amount
        """
        if days_in_period <= 0:
            return 0.0

        # For dynamic pricing, proration is based on the base price * default_multiplier
        full_price = self.base_price * self.default_multiplier * quantity
        return full_price * (days_used / days_in_period)

    def validate_plan_change(
        self, current_plan: Dict[str, Any], new_plan: Dict[str, Any]
    ) -> bool:
        """
        Validate if a plan change is allowed.

        Args:
            current_plan: Current plan details
            new_plan: New plan details to switch to

        Returns:
            True if the plan change is allowed, False otherwise
        """
        # In dynamic pricing, we allow all plan changes by default
        return True
