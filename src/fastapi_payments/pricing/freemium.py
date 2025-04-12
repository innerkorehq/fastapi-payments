"""Freemium pricing model implementation."""

from .base import PricingStrategy
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta


class FreemiumPricing(PricingStrategy):
    """
    Freemium pricing strategy with free tier and paid upgrades.
    """

    def __init__(
        self, base_price=0.0, free_tier_limit=0, paid_tier_price=0.0, tax_rate=0.0
    ):
        """
        Initialize the freemium pricing strategy.

        Args:
            base_price: Base price (usually 0 for freemium)
            free_tier_limit: Usage limit for free tier
            paid_tier_price: Price for paid tier
            tax_rate: Tax rate
        """
        self.base_price = base_price
        self.free_tier_limit = free_tier_limit
        self.paid_tier_price = paid_tier_price
        self.tax_rate = tax_rate

    def calculate_price(self, usage=0, tax_rate=None) -> float:
        """
        Calculate price using freemium model.

        Args:
            usage: Usage units
            tax_rate: Override default tax rate (optional)

        Returns:
            Calculated total price (0 if within free tier)
        """
        tax_rate = tax_rate if tax_rate is not None else self.tax_rate

        # Check if usage is within free tier
        if usage <= self.free_tier_limit:
            return self.base_price  # Usually 0

        # Calculate paid tier price
        subtotal = self.paid_tier_price
        tax_amount = subtotal * tax_rate
        return subtotal + tax_amount

    def get_billing_items(self, usage=0):
        """
        Get itemized billing details.

        Args:
            usage: Usage units

        Returns:
            List of billing items
        """
        items = []

        # Add base tier item (usually free)
        if self.base_price > 0:
            items.append(
                {
                    "description": "Base tier",
                    "quantity": 1,
                    "unit_price": self.base_price,
                    "amount": self.base_price,
                }
            )

        # Add paid tier if exceeding free limit
        if usage > self.free_tier_limit:
            items.append(
                {
                    "description": f"Paid tier (exceeded {self.free_tier_limit} free units)",
                    "quantity": 1,
                    "unit_price": self.paid_tier_price,
                    "amount": self.paid_tier_price,
                }
            )

        return items

    def calculate_proration(self, days_used, days_in_period, usage=0) -> float:
        """
        Calculate prorated amount for paid tier.

        Args:
            days_used: Days used in period
            days_in_period: Total days in period
            usage: Current usage level

        Returns:
            Prorated price (0 if in free tier)
        """
        if days_in_period <= 0:
            return 0.0

        # If usage is within free tier, no proration needed (always free)
        if usage <= self.free_tier_limit:
            return 0.0

        # For paid tier, prorate the paid tier price
        full_price = self.paid_tier_price
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
        # Freemium plans typically allow all changes
        return True
