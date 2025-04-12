"""Hybrid pricing model implementation."""

from .base import PricingStrategy
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta


class HybridPricing(PricingStrategy):
    """
    Hybrid pricing strategy combining subscription and usage-based billing.
    """

    def __init__(self, base_price, usage_rate=0.0, tax_rate=0.0):
        """
        Initialize the hybrid pricing strategy.

        Args:
            base_price: Base subscription price
            usage_rate: Price per usage unit
            tax_rate: Tax rate
        """
        self.base_price = base_price
        self.usage_rate = usage_rate
        self.tax_rate = tax_rate

    def calculate_price(self, quantity=1, usage=0, tax_rate=None):
        """
        Calculate price using hybrid pricing model.

        Args:
            quantity: Subscription quantity
            usage: Usage units
            tax_rate: Override default tax rate (optional)

        Returns:
            Calculated total price
        """
        tax_rate = tax_rate if tax_rate is not None else self.tax_rate
        subscription_cost = self.base_price * quantity
        usage_cost = usage * self.usage_rate
        subtotal = subscription_cost + usage_cost
        tax_amount = subtotal * tax_rate
        return subtotal + tax_amount

    def get_billing_items(self, quantity=1, usage=0):
        """
        Get itemized billing details.

        Args:
            quantity: Subscription quantity
            usage: Usage units

        Returns:
            List of billing items
        """
        subscription_cost = self.base_price * quantity
        usage_cost = usage * self.usage_rate

        items = [
            {
                "description": f"Subscription ({quantity} units)",
                "quantity": quantity,
                "unit_price": self.base_price,
                "amount": subscription_cost,
            }
        ]

        # Add usage item if applicable
        if usage > 0 and self.usage_rate > 0:
            items.append(
                {
                    "description": f"Usage ({usage} units)",
                    "quantity": usage,
                    "unit_price": self.usage_rate,
                    "amount": usage_cost,
                }
            )

        return items

    def calculate_proration(self, days_used, days_in_period, quantity=1):
        """
        Calculate prorated subscription amount.

        Args:
            days_used: Days used in period
            days_in_period: Total days in period
            quantity: Subscription quantity

        Returns:
            Prorated subscription price
        """
        if days_in_period <= 0:
            return 0.0

        full_price = self.base_price * quantity
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
        # In the hybrid pricing model, we allow all plan changes by default
        # This could be customized based on business rules
        return True
