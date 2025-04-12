from .base import PricingStrategy
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta


class SubscriptionPricing(PricingStrategy):
    """Pricing strategy for subscription-based pricing."""

    async def calculate_price(
        self,
        base_amount: float,
        quantity: int = 1,
        discount_percentage: Optional[float] = None,
        discount_amount: Optional[float] = None,
        tax_rate: Optional[float] = None,
        **kwargs,
    ) -> float:
        """
        Calculate the final price for a subscription.

        Args:
            base_amount: Base price of the subscription
            quantity: Number of units/seats
            discount_percentage: Optional percentage discount (0.0 to 1.0)
            discount_amount: Optional fixed discount amount
            tax_rate: Optional tax rate override

        Returns:
            Final calculated price
        """
        # Calculate base price with quantity
        total = base_amount * quantity

        # Apply percentage discount if provided
        if discount_percentage and 0 <= discount_percentage <= 1:
            total = total * (1 - discount_percentage)

        # Apply fixed discount if provided
        if discount_amount and discount_amount > 0:
            total = max(0, total - discount_amount)

        # Round before applying tax
        total = self.round_price(total)

        # Apply tax
        total = self.apply_tax(total, tax_rate)

        return total

    async def calculate_proration(
        self,
        previous_plan: Dict[str, Any],
        new_plan: Dict[str, Any],
        days_used: int,
        days_in_period: int,
    ) -> float:
        """
        Calculate the prorated amount when changing plans.

        Args:
            previous_plan: Original plan details
            new_plan: New plan details
            days_used: Number of days used in current period
            days_in_period: Total days in billing period

        Returns:
            Prorated amount for the billing adjustment
        """
        if days_in_period <= 0:
            return 0

        # Calculate unused portion of current plan
        unused_ratio = (days_in_period - days_used) / days_in_period
        unused_amount = previous_plan["amount"] * unused_ratio

        # Calculate cost of new plan for remaining period
        remaining_ratio = unused_ratio
        new_plan_cost = new_plan["amount"] * remaining_ratio

        # Calculate the adjustment (can be positive or negative)
        adjustment = new_plan_cost - unused_amount

        return self.round_price(adjustment)

    async def get_billing_items(
        self,
        plan_id: str,
        plan_name: str,
        plan_amount: float,
        quantity: int = 1,
        period_start: datetime = None,
        period_end: datetime = None,
        discount_percentage: Optional[float] = None,
        discount_amount: Optional[float] = None,
        tax_rate: Optional[float] = None,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """
        Get billing items for a subscription.

        Returns:
            List of billing items including base subscription, discounts, and taxes
        """
        if not period_start:
            period_start = datetime.utcnow()
        if not period_end:
            # Default to 1 month if not specified
            period_end = period_start + timedelta(days=30)

        base_price = plan_amount * quantity
        items = [
            {
                "type": "subscription",
                "plan_id": plan_id,
                "name": plan_name,
                "description": f"{plan_name} subscription",
                "amount": base_price,
                "quantity": quantity,
                "unit_price": plan_amount,
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
            }
        ]

        # Add percentage discount if applicable
        if discount_percentage and 0 < discount_percentage <= 1:
            discount_value = base_price * discount_percentage
            items.append(
                {
                    "type": "discount",
                    "name": "Percentage Discount",
                    "description": f"{int(discount_percentage * 100)}% discount",
                    "amount": -discount_value,
                    "quantity": 1,
                }
            )
            base_price -= discount_value

        # Add fixed discount if applicable
        if discount_amount and discount_amount > 0:
            items.append(
                {
                    "type": "discount",
                    "name": "Fixed Discount",
                    "description": f"Fixed discount",
                    "amount": -min(
                        discount_amount, base_price
                    ),  # Don't discount more than base price
                    "quantity": 1,
                }
            )
            base_price = max(0, base_price - discount_amount)

        # Add tax if applicable
        if not self.config.tax.included_in_price and (
            self.config.tax.default_rate > 0 or (tax_rate and tax_rate > 0)
        ):
            effective_tax_rate = (
                tax_rate if tax_rate is not None else self.config.tax.default_rate
            )
            if effective_tax_rate > 0:
                tax_amount = self.calculate_tax_amount(
                    base_price, effective_tax_rate)
                items.append(
                    {
                        "type": "tax",
                        "name": "Tax",
                        "description": f"Tax ({int(effective_tax_rate * 100)}%)",
                        "amount": tax_amount,
                        "quantity": 1,
                    }
                )

        return items

    async def validate_plan_change(
        self, current_plan: Dict[str, Any], new_plan: Dict[str, Any]
    ) -> bool:
        """
        Validate if a subscription plan change is allowed.

        Args:
            current_plan: Current plan details
            new_plan: New plan details

        Returns:
            True if the plan change is allowed, False otherwise
        """
        # Example validation logic - can be customized based on business rules

        # Check if plans have compatible intervals
        if current_plan.get("billing_interval") != new_plan.get("billing_interval"):
            # Only allow changes between plans with the same interval (monthly->monthly, yearly->yearly)
            return False

        # If downgrading from a yearly to a monthly plan (for same interval)
        if (
            current_plan.get("amount", 0) > new_plan.get("amount", 0)
            and current_plan.get("billing_interval") == "yearly"
        ):
            # Disallow downgrades during annual commitment
            return False

        # By default, allow the change
        return True
