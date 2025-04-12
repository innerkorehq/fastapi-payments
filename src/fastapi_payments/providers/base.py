"""Base payment provider interface."""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from datetime import datetime
from ..config.config_schema import ProviderConfig


class PaymentProvider(ABC):
    """Base payment provider class."""

    def __init__(self, config):
        """
        Initialize the payment provider.

        Args:
            config: Configuration object or dictionary
        """
        # Convert dictionary to ProviderConfig if needed
        if isinstance(config, dict):
            self.config = ProviderConfig(**config)
        else:
            self.config = config

        self.initialize()

    @abstractmethod
    def initialize(self):
        """Initialize the provider with configuration."""
        pass

    @abstractmethod
    async def create_customer(
        self,
        email: str,
        name: Optional[str] = None,
        meta_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a customer in the provider's system.

        Args:
            email: Customer email
            name: Customer name
            meta_info: Additional customer meta_info

        Returns:
            Customer data dictionary
        """
        pass

    @abstractmethod
    async def retrieve_customer(self, provider_customer_id: str) -> Dict[str, Any]:
        """
        Retrieve customer data from the provider.

        Args:
            provider_customer_id: Customer ID in the provider's system

        Returns:
            Customer data dictionary
        """
        pass

    @abstractmethod
    async def update_customer(
        self, provider_customer_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update customer data in the provider's system.

        Args:
            provider_customer_id: Customer ID in the provider's system
            data: Updated customer data

        Returns:
            Updated customer data
        """
        pass

    @abstractmethod
    async def delete_customer(self, provider_customer_id: str) -> Dict[str, Any]:
        """
        Delete a customer from the provider's system.

        Args:
            provider_customer_id: Customer ID in the provider's system

        Returns:
            Deletion confirmation
        """
        pass

    @abstractmethod
    async def create_payment_method(
        self, provider_customer_id: str, payment_details: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a payment method for a customer.

        Args:
            provider_customer_id: Customer ID in the provider's system
            payment_details: Payment method details

        Returns:
            Payment method data
        """
        pass

    @abstractmethod
    async def list_payment_methods(
        self, provider_customer_id: str
    ) -> List[Dict[str, Any]]:
        """
        List payment methods for a customer.

        Args:
            provider_customer_id: Customer ID in the provider's system

        Returns:
            List of payment methods
        """
        pass

    @abstractmethod
    async def delete_payment_method(self, payment_method_id: str) -> Dict[str, Any]:
        """
        Delete a payment method.

        Args:
            payment_method_id: Payment method ID

        Returns:
            Deletion confirmation
        """
        pass

    @abstractmethod
    async def create_product(
        self,
        name: str,
        description: Optional[str] = None,
        meta_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a product in the provider's system.

        Args:
            name: Product name
            description: Product description
            meta_info: Additional product meta_info

        Returns:
            Product data
        """
        pass

    @abstractmethod
    async def create_price(
        self,
        product_id: str,
        amount: float,
        currency: str,
        interval: Optional[str] = None,
        interval_count: Optional[int] = None,
        meta_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a price for a product.

        Args:
            product_id: Product ID
            amount: Price amount
            currency: Price currency
            interval: Billing interval (month, year, etc.)
            interval_count: Number of intervals
            meta_info: Additional price meta_info

        Returns:
            Price data
        """
        pass

    @abstractmethod
    async def create_subscription(
        self,
        provider_customer_id: str,
        price_id: str,
        quantity: int = 1,
        trial_period_days: Optional[int] = None,
        meta_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a subscription for a customer.

        Args:
            provider_customer_id: Customer ID in the provider's system
            price_id: Price ID
            quantity: Subscription quantity
            trial_period_days: Number of trial days
            meta_info: Additional subscription meta_info

        Returns:
            Subscription data
        """
        pass

    @abstractmethod
    async def retrieve_subscription(
        self, provider_subscription_id: str
    ) -> Dict[str, Any]:
        """
        Retrieve subscription details.

        Args:
            provider_subscription_id: Subscription ID in the provider's system

        Returns:
            Subscription data
        """
        pass

    @abstractmethod
    async def update_subscription(
        self, provider_subscription_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update subscription details.

        Args:
            provider_subscription_id: Subscription ID in the provider's system
            data: Updated subscription data

        Returns:
            Updated subscription data
        """
        pass

    @abstractmethod
    async def cancel_subscription(
        self, provider_subscription_id: str, cancel_at_period_end: bool = True
    ) -> Dict[str, Any]:
        """
        Cancel a subscription.

        Args:
            provider_subscription_id: Subscription ID in the provider's system
            cancel_at_period_end: Whether to cancel at the end of the current period

        Returns:
            Canceled subscription data
        """
        pass

    @abstractmethod
    async def process_payment(
        self,
        amount: float,
        currency: str,
        provider_customer_id: Optional[str] = None,
        payment_method_id: Optional[str] = None,
        description: Optional[str] = None,
        meta_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Process a one-time payment.

        Args:
            amount: Payment amount
            currency: Payment currency
            provider_customer_id: Customer ID in the provider's system
            payment_method_id: Payment method ID
            description: Payment description
            meta_info: Additional payment meta_info

        Returns:
            Payment data
        """
        pass

    @abstractmethod
    async def refund_payment(
        self, provider_payment_id: str, amount: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Refund a payment.

        Args:
            provider_payment_id: Payment ID in the provider's system
            amount: Amount to refund

        Returns:
            Refund data
        """
        pass

    @abstractmethod
    async def webhook_handler(
        self, payload: Dict[str, Any], signature: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Handle webhook events from the provider.

        Args:
            payload: Webhook payload
            signature: Webhook signature

        Returns:
            Processed event data with standardized fields
        """
        pass

    async def record_usage(
        self,
        subscription_item_id: str,
        quantity: int,
        timestamp: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Record usage for usage-based billing.

        Args:
            subscription_item_id: Subscription item ID
            quantity: Usage quantity
            timestamp: Usage timestamp

        Returns:
            Usage record data
        """
        # Default implementation - providers should override as needed
        raise NotImplementedError(
            "Usage-based billing not supported by this provider")
