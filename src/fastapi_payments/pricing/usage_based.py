"""Usage-based pricing model implementation."""

from .base import PricingStrategy
from typing import Dict, Any, Optional, List


class UsageBasedPricing(PricingStrategy):
    """
    Usage-based pricing strategy that charges based on consumption.
    """

    def __init__(
        self, price_per_unit, minimum_charge=0.0, maximum_charge=None, tax_rate=0.0
    ):
        """
        Initialize the usage-based pricing strategy.

        Args:
            price_per_unit: Price per unit of usage
            minimum_charge: Minimum charge regardless of usage
            maximum_charge: Maximum charge cap (optional)
            tax_rate: Tax rate
        """
        self.price_per_unit = price_per_unit
        self.minimum_charge = minimum_charge
        self.maximum_charge = maximum_charge
        self.tax_rate = tax_rate

    def calculate_price(self, usage=0, tax_rate=None) -> float:
        """
        Calculate price using usage-based model.

        Args:
            usage: Usage units
            tax_rate: Override default tax rate (optional)

        Returns:
            Calculated total price
        """
        tax_rate = tax_rate if tax_rate is not None else self.tax_rate

        # Calculate base amount from usage
        amount = usage * self.price_per_unit

        # Apply minimum charge if needed
        if amount < self.minimum_charge:
            amount = self.minimum_charge

        # Apply maximum charge cap if specified
        if self.maximum_charge is not None and amount > self.maximum_charge:
            amount = self.maximum_charge

        # Apply tax
        total = amount * (1 + tax_rate)

        return total

    def get_billing_items(self, usage=0) -> List[Dict[str, Any]]:
        """
        Get itemized billing details.

        Args:
            usage: Usage units

        Returns:
            List of billing items
        """
        base_amount = usage * self.price_per_unit
        billable_amount = base_amount
        items = []

        # Create base usage item
        items.append(
            {
                "description": f"Usage ({usage} units)",
                "quantity": usage,
                "unit_price": self.price_per_unit,
                "amount": base_amount,
            }
        )

        # Add minimum charge adjustment if needed
        if base_amount < self.minimum_charge:
            adjustment = self.minimum_charge - base_amount
            items.append(
                {
                    "description": "Minimum charge adjustment",
                    "quantity": 1,
                    "unit_price": adjustment,
                    "amount": adjustment,
                }
            )
            billable_amount = self.minimum_charge

        # Add maximum charge adjustment if needed
        if self.maximum_charge is not None and base_amount > self.maximum_charge:
            adjustment = self.maximum_charge - base_amount
            items.append(
                {
                    "description": "Maximum charge adjustment",
                    "quantity": 1,
                    "unit_price": adjustment,
                    "amount": adjustment,
                }
            )
            billable_amount = self.maximum_charge

        return items

    def calculate_proration(self, days_used, days_in_period, usage=0) -> float:
        """
        Calculate prorated amount.

        Args:
            days_used: Days used in period
            days_in_period: Total days in period
            usage: Usage units

        Returns:
            Prorated price
        """
        if days_in_period <= 0:
            return 0.0

        # For usage-based, we don't typically prorate based on days
        # as the billing is directly tied to usage
        # But we can prorate any minimum charges
        if self.minimum_charge > 0:
            prorated_minimum = self.minimum_charge * \
                (days_used / days_in_period)
            usage_amount = usage * self.price_per_unit

            # Return the greater of prorated minimum or actual usage
            return max(prorated_minimum, usage_amount)
        else:
            # Just return the usage-based amount
            return usage * self.price_per_unit

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
        # Usage-based plans typically allow all changes
        return True
