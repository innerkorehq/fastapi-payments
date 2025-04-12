from typing import Dict, Any, Optional, List, Type
from ..config.config_schema import PaymentConfig
from ..pricing.base import PricingStrategy
from ..pricing.subscription import SubscriptionPricing
from ..pricing.usage_based import UsageBasedPricing
from ..pricing.tiered import TieredPricing
import importlib
import logging

logger = logging.getLogger(__name__)


class PricingService:
    """Service for handling pricing calculations and operations."""

    def __init__(self, config: PaymentConfig):
        """
        Initialize the pricing service.

        Args:
            config: Payment configuration
        """
        self.config = config
        self.pricing_strategies = {}
        self._initialize_pricing_strategies()

        logger.info(
            f"Pricing service initialized with strategies: {
                ', '.join(self.pricing_strategies.keys())}"
        )

    def _initialize_pricing_strategies(self):
        """Initialize pricing strategies."""
        # Built-in pricing strategies
        self.pricing_strategies = {
            "subscription": SubscriptionPricing(self.config.pricing),
            "usage_based": UsageBasedPricing(self.config.pricing),
            "tiered": TieredPricing(self.config.pricing),
        }

        # Add more built-in strategies
        try:
            from ..pricing.per_user import PerUserPricing

            self.pricing_strategies["per_user"] = PerUserPricing(
                self.config.pricing)
        except ImportError:
            logger.warning("PerUserPricing strategy not found")

        try:
            from ..pricing.freemium import FreemiumPricing

            self.pricing_strategies["freemium"] = FreemiumPricing(
                self.config.pricing)
        except ImportError:
            logger.warning("FreemiumPricing strategy not found")

        try:
            from ..pricing.dynamic import DynamicPricing

            self.pricing_strategies["dynamic"] = DynamicPricing(
                self.config.pricing)
        except ImportError:
            logger.warning("DynamicPricing strategy not found")

        try:
            from ..pricing.hybrid import HybridPricing

            self.pricing_strategies["hybrid"] = HybridPricing(
                self.config.pricing)
        except ImportError:
            logger.warning("HybridPricing strategy not found")

        # Load custom pricing strategies from configuration
        custom_strategies = (
            self.config.pricing.additional_settings.get(
                "custom_strategies", {})
            if hasattr(self.config.pricing, "additional_settings")
            else {}
        )

        for strategy_name, class_path in custom_strategies.items():
            try:
                module_path, class_name = class_path.rsplit(".", 1)
                module = importlib.import_module(module_path)
                strategy_class = getattr(module, class_name)
                self.pricing_strategies[strategy_name] = strategy_class(
                    self.config.pricing
                )
                logger.info(f"Loaded custom pricing strategy: {strategy_name}")
            except (ValueError, ImportError, AttributeError) as e:
                logger.error(
                    f"Failed to load pricing strategy '{
                        strategy_name}': {str(e)}"
                )

    def get_strategy(self, pricing_model: str) -> Optional[PricingStrategy]:
        """
        Get a pricing strategy instance.

        Args:
            pricing_model: Pricing model name

        Returns:
            Pricing strategy instance if found, None otherwise
        """
        return self.pricing_strategies.get(pricing_model.lower())

    async def is_valid_pricing_model(self, pricing_model: str) -> bool:
        """
        Check if a pricing model is valid.

        Args:
            pricing_model: Pricing model name

        Returns:
            True if valid, False otherwise
        """
        return pricing_model.lower() in self.pricing_strategies

    async def calculate_price(self, pricing_model: str, **kwargs) -> float:
        """
        Calculate price based on the specified pricing model.

        Args:
            pricing_model: Pricing model name
            **kwargs: Parameters for price calculation

        Returns:
            Calculated price

        Raises:
            ValueError: If pricing model is not found
        """
        strategy = self.get_strategy(pricing_model)

        if not strategy:
            raise ValueError(f"Pricing model not found: {pricing_model}")

        return await strategy.calculate_price(**kwargs)

    async def calculate_proration(
        self,
        pricing_model: str,
        previous_plan: Dict[str, Any],
        new_plan: Dict[str, Any],
        days_used: int,
        days_in_period: int,
    ) -> float:
        """
        Calculate prorated amount for plan changes.

        Args:
            pricing_model: Pricing model name
            previous_plan: Original plan details
            new_plan: New plan details
            days_used: Number of days used in current period
            days_in_period: Total days in billing period

        Returns:
            Prorated amount

        Raises:
            ValueError: If pricing model is not found
        """
        strategy = self.get_strategy(pricing_model)

        if not strategy:
            raise ValueError(f"Pricing model not found: {pricing_model}")

        return await strategy.calculate_proration(
            previous_plan, new_plan, days_used, days_in_period
        )

    async def get_billing_items(
        self, pricing_model: str, **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Get billing items based on the pricing model.

        Args:
            pricing_model: Pricing model name
            **kwargs: Parameters for billing items

        Returns:
            List of billing items

        Raises:
            ValueError: If pricing model is not found
        """
        strategy = self.get_strategy(pricing_model)

        if not strategy:
            raise ValueError(f"Pricing model not found: {pricing_model}")

        return await strategy.get_billing_items(**kwargs)

    async def validate_plan_change(
        self, pricing_model: str, current_plan: Dict[str, Any], new_plan: Dict[str, Any]
    ) -> bool:
        """
        Validate if a plan change is allowed.

        Args:
            pricing_model: Pricing model name
            current_plan: Current plan details
            new_plan: New plan details

        Returns:
            True if the plan change is allowed, False otherwise

        Raises:
            ValueError: If pricing model is not found
        """
        strategy = self.get_strategy(pricing_model)

        if not strategy:
            raise ValueError(f"Pricing model not found: {pricing_model}")

        return await strategy.validate_plan_change(current_plan, new_plan)
