from typing import Dict, Any, Optional, List
import logging
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from ..config.config_schema import PaymentConfig
from ..providers import get_provider
from ..messaging.publishers import PaymentEventPublisher, PaymentEvents
from ..db.repositories import (
    CustomerRepository,
    PaymentRepository,
    SubscriptionRepository,
    ProductRepository,
    PlanRepository,
)

logger = logging.getLogger(__name__)


class PaymentService:
    """Service for payment operations."""

    def __init__(
        self,
        config: PaymentConfig,
        event_publisher: PaymentEventPublisher,
        db_session=None,
    ):
        """
        Initialize the payment service.

        Args:
            config: Payment configuration
            event_publisher: Event publisher for notifications
            db_session: Database session
        """
        self.config = config
        self.default_provider = config.default_provider
        self.event_publisher = event_publisher
        self.db_session = db_session

        # Initialize provider instances
        self.providers = {}
        for provider_name, provider_config in config.providers.items():
            self.providers[provider_name] = get_provider(
                provider_name, provider_config)

        # Initialize repositories if session is provided
        if db_session:
            self.customer_repo = CustomerRepository(db_session)
            self.payment_repo = PaymentRepository(db_session)
            self.subscription_repo = SubscriptionRepository(db_session)
            self.product_repo = ProductRepository(db_session)
            self.plan_repo = PlanRepository(db_session)

    def set_db_session(self, session: AsyncSession):
        """
        Set the database session.

        Args:
            session: SQLAlchemy AsyncSession
        """
        self.db_session = session
        self.customer_repo = CustomerRepository(session)
        self.payment_repo = PaymentRepository(session)
        self.subscription_repo = SubscriptionRepository(session)
        self.product_repo = ProductRepository(session)
        self.plan_repo = PlanRepository(session)

    def get_provider(self, provider_name: Optional[str] = None) -> Any:
        """
        Get a payment provider instance.

        Args:
            provider_name: Name of the provider to get, or None for default

        Returns:
            Provider instance
        """
        provider_name = provider_name or self.default_provider
        provider = self.providers.get(provider_name)
        if not provider:
            raise ValueError(f"Provider {provider_name} not found")
        return provider

    async def create_customer(
        self,
        email: str,
        name: Optional[str] = None,
        meta_info: Optional[Dict[str, Any]] = None,
        provider: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a customer.

        Args:
            email: Customer email
            name: Customer name
            meta_info: Additional customer meta_info
            provider: Name of the provider to use (default is default_provider)

        Returns:
            Customer data dictionary
        """
        provider_instance = self.get_provider(provider)
        customer_data = await provider_instance.create_customer(
            email=email, name=name, meta_info=meta_info
        )

        # Save to database if session available
        if hasattr(self, "customer_repo"):
            customer = await self.customer_repo.create(
                email=email, name=name, meta_info=meta_info
            )

            # Link the provider's customer ID to our customer
            await self.customer_repo.add_provider_customer(
                customer_id=customer.id,
                provider=provider or self.default_provider,
                provider_customer_id=customer_data["provider_customer_id"],
            )

            # Return standardized customer data
            return {
                "id": customer.id,
                "email": customer.email,
                "name": customer.name,
                "created_at": customer.created_at.isoformat(),
                "provider_customer_id": customer_data["provider_customer_id"],
            }
        else:
            # No database session, return the provider's response directly
            return {
                "id": f"cust_{hash(email) % 10000:04d}",  # Generate a fake ID
                **customer_data,
            }

    async def get_customer(self, customer_id: str) -> Optional[Dict[str, Any]]:
        """
        Get customer details.

        Args:
            customer_id: Customer ID

        Returns:
            Customer data if found, None otherwise
        """
        if not self.db_session:
            raise RuntimeError("Database session not set")

        customer_repo = CustomerRepository(self.db_session)
        customer = await customer_repo.get_with_provider_customers(customer_id)

        if not customer:
            return None

        # Get provider-specific data for each provider
        provider_data = {}
        for provider_customer in customer.provider_customers:
            provider_instance = self.get_provider(provider_customer.provider)
            try:
                provider_data[provider_customer.provider] = (
                    await provider_instance.retrieve_customer(
                        provider_customer.provider_customer_id
                    )
                )
            except Exception as e:
                logger.error(f"Error retrieving provider customer: {str(e)}")
                provider_data[provider_customer.provider] = {"error": str(e)}

        # Return combined data
        return {
            "id": customer.id,
            "email": customer.email,
            "name": customer.name,
            "meta_info": customer.meta_info,
            "created_at": customer.created_at.isoformat(),
            "updated_at": customer.updated_at.isoformat(),
            "provider_customers": [
                {
                    "provider": pc.provider,
                    "provider_customer_id": pc.provider_customer_id,
                    "provider_data": provider_data.get(pc.provider, {}),
                }
                for pc in customer.provider_customers
            ],
        }

    async def update_customer(self, customer_id: str, **kwargs) -> Dict[str, Any]:
        """
        Update customer details.

        Args:
            customer_id: Customer ID
            **kwargs: Fields to update

        Returns:
            Updated customer data
        """
        if not self.db_session:
            raise RuntimeError("Database session not set")

        customer_repo = CustomerRepository(self.db_session)
        customer = await customer_repo.get_with_provider_customers(customer_id)

        if not customer:
            raise ValueError(f"Customer not found: {customer_id}")

        # Update customer in database
        update_fields = {}
        for field in ["email", "name", "meta_info"]:
            if field in kwargs:
                update_fields[field] = kwargs[field]

        if update_fields:
            customer = await customer_repo.update(customer_id, **update_fields)

        # Update customer in providers
        for provider_customer in customer.provider_customers:
            provider_instance = self.get_provider(provider_customer.provider)
            try:
                await provider_instance.update_customer(
                    provider_customer.provider_customer_id, **kwargs
                )
            except Exception as e:
                logger.error(f"Error updating provider customer: {str(e)}")

        # Publish event
        await self.event_publisher.publish_event(
            PaymentEvents.CUSTOMER_UPDATED,
            {"customer_id": customer.id, "updates": update_fields},
        )

        # Return updated customer
        return await self.get_customer(customer_id)

    async def create_payment_method(
        self,
        customer_id: str,
        payment_details: Dict[str, Any],
        provider: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a payment method for a customer.

        Args:
            customer_id: Customer ID
            payment_details: Payment method details
            provider: Optional provider name

        Returns:
            Created payment method data
        """
        if not self.db_session:
            raise RuntimeError("Database session not set")

        provider_name = provider or self.default_provider
        customer_repo = CustomerRepository(self.db_session)

        # Get provider customer
        provider_customer = await customer_repo.get_provider_customer(
            customer_id, provider_name
        )
        if not provider_customer:
            raise ValueError(
                f"Customer not found for provider {provider_name}")

        # Create payment method in provider
        provider_instance = self.get_provider(provider_name)
        payment_method = await provider_instance.create_payment_method(
            provider_customer.provider_customer_id, payment_details
        )

        # Publish event
        await self.event_publisher.publish_event(
            PaymentEvents.PAYMENT_METHOD_CREATED,
            {
                "customer_id": customer_id,
                "provider": provider_name,
                "payment_method_id": payment_method["payment_method_id"],
            },
        )

        # Return payment method data
        return {
            "id": payment_method["payment_method_id"],
            "provider": provider_name,
            "type": payment_method.get("type"),
            "is_default": payment_method.get("is_default", False),
            "card": payment_method.get("card"),
            "created_at": datetime.utcnow().isoformat(),
        }

    async def list_payment_methods(
        self, customer_id: str, provider: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List payment methods for a customer.

        Args:
            customer_id: Customer ID
            provider: Optional provider name

        Returns:
            List of payment methods
        """
        if not self.db_session:
            raise RuntimeError("Database session not set")

        provider_name = provider or self.default_provider
        customer_repo = CustomerRepository(self.db_session)

        # Get provider customer
        provider_customer = await customer_repo.get_provider_customer(
            customer_id, provider_name
        )
        if not provider_customer:
            raise ValueError(
                f"Customer not found for provider {provider_name}")

        # List payment methods from provider
        provider_instance = self.get_provider(provider_name)
        payment_methods = await provider_instance.list_payment_methods(
            provider_customer.provider_customer_id
        )

        # Return formatted payment methods
        return [
            {
                "id": pm["payment_method_id"],
                "provider": provider_name,
                "type": pm.get("type"),
                "is_default": pm.get("is_default", False),
                "card": pm.get("card"),
            }
            for pm in payment_methods
        ]

    async def create_product(
        self,
        name: str,
        description: Optional[str] = None,
        provider: Optional[str] = None,
        meta_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a new product.

        Args:
            name: Product name
            description: Optional product description
            provider: Optional provider name
            meta_info: Optional product meta_info

        Returns:
            Created product data
        """
        if not self.db_session:
            raise RuntimeError("Database session not set")

        provider_name = provider or self.default_provider
        provider_instance = self.get_provider(provider_name)

        # Create product in provider
        provider_product = await provider_instance.create_product(
            name=name, description=description, meta_info=meta_info
        )

        # Create product in database
        product_repo = ProductRepository(self.db_session)
        product = await product_repo.create(
            name=name,
            description=description,
            meta_info={
                **(meta_info or {}),
                "provider_product_id": provider_product["provider_product_id"],
                "provider": provider_name,
            },
        )

        # Return combined data
        return {
            "id": product.id,
            "name": product.name,
            "description": product.description,
            "active": product.active,
            "provider_product_id": provider_product["provider_product_id"],
            "provider": provider_name,
            "created_at": product.created_at.isoformat(),
        }

    async def create_plan(
        self,
        product_id: str,
        name: str,
        pricing_model: str,
        amount: float,
        description: Optional[str] = None,
        currency: str = "USD",
        billing_interval: Optional[str] = None,
        billing_interval_count: Optional[int] = None,
        trial_period_days: Optional[int] = None,
        provider: Optional[str] = None,
        meta_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a plan for a product.

        Args:
            product_id: Product ID
            name: Plan name
            pricing_model: Pricing model (subscription, usage_based, etc.)
            amount: Base amount
            description: Optional plan description
            currency: Currency code
            billing_interval: Billing interval (day, week, month, year)
            billing_interval_count: Number of intervals between billings
            trial_period_days: Optional trial period in days
            provider: Optional provider name
            meta_info: Optional plan meta_info

        Returns:
            Created plan data
        """
        if not self.db_session:
            raise RuntimeError("Database session not set")

        provider_name = provider or self.default_provider
        provider_instance = self.get_provider(provider_name)

        # Get product
        product_repo = ProductRepository(self.db_session)
        product = await product_repo.get_by_id(product_id)

        if not product:
            raise ValueError(f"Product not found: {product_id}")

        # Get provider product ID from meta_info
        provider_product_id = product.meta_info.get("provider_product_id")
        if not provider_product_id:
            raise ValueError(
                f"Provider product ID not found for product {product_id}")

        # Create price in provider
        provider_price = await provider_instance.create_price(
            product_id=provider_product_id,
            amount=amount,
            currency=currency,
            interval=billing_interval,
            interval_count=billing_interval_count,
            meta_info={
                **(meta_info or {}),
                "name": name,
                "pricing_model": pricing_model,
            },
        )

        # Create plan in database
        plan_repo = PlanRepository(self.db_session)
        plan = await plan_repo.create(
            product_id=product_id,
            name=name,
            description=description,
            pricing_model=pricing_model,
            amount=amount,
            currency=currency,
            billing_interval=billing_interval,
            billing_interval_count=billing_interval_count,
            trial_period_days=trial_period_days,
            is_active=True,
            meta_info={
                **(meta_info or {}),
                "provider": provider_name,
                "provider_price_id": provider_price["provider_price_id"],
            },
        )

        # Return combined data
        return {
            "id": plan.id,
            "product_id": plan.product_id,
            "name": plan.name,
            "description": plan.description,
            "pricing_model": plan.pricing_model,
            "amount": plan.amount,
            "currency": plan.currency,
            "billing_interval": plan.billing_interval,
            "billing_interval_count": plan.billing_interval_count,
            "trial_period_days": plan.trial_period_days,
            "provider": provider_name,
            "provider_price_id": provider_price["provider_price_id"],
            "created_at": plan.created_at.isoformat(),
        }

    async def create_subscription(
        self,
        customer_id: str,
        plan_id: str,
        quantity: int = 1,
        trial_period_days: Optional[int] = None,
        meta_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a subscription for a customer.

        Args:
            customer_id: Customer ID
            plan_id: Plan ID
            quantity: Number of units/seats
            trial_period_days: Optional trial period in days
            meta_info: Optional subscription meta_info

        Returns:
            Created subscription data
        """
        if not self.db_session:
            raise RuntimeError("Database session not set")

        # Get plan and customer
        plan_repo = PlanRepository(self.db_session)
        customer_repo = CustomerRepository(self.db_session)

        plan = await plan_repo.get_by_id(plan_id)
        customer = await customer_repo.get_with_provider_customers(customer_id)

        if not plan:
            raise ValueError(f"Plan not found: {plan_id}")

        if not customer:
            raise ValueError(f"Customer not found: {customer_id}")

        # Get provider from plan meta_info
        provider_name = plan.meta_info.get("provider")
        provider_price_id = plan.meta_info.get("provider_price_id")

        if not provider_name or not provider_price_id:
            raise ValueError(f"Provider info not found for plan {plan_id}")

        # Get provider customer
        provider_customer = await customer_repo.get_provider_customer(
            customer_id, provider_name
        )
        if not provider_customer:
            raise ValueError(
                f"Customer not found for provider {provider_name}")

        # Create subscription in provider
        provider_instance = self.get_provider(provider_name)
        provider_subscription = await provider_instance.create_subscription(
            provider_customer_id=provider_customer.provider_customer_id,
            price_id=provider_price_id,
            quantity=quantity,
            trial_period_days=trial_period_days or plan.trial_period_days,
            meta_info=meta_info,
        )

        # Create subscription in database
        subscription_repo = SubscriptionRepository(self.db_session)
        current_period_start = (
            datetime.fromisoformat(
                provider_subscription["current_period_start"].replace(
                    "Z", "+00:00")
            )
            if isinstance(provider_subscription["current_period_start"], str)
            else provider_subscription["current_period_start"]
        )

        current_period_end = None
        if provider_subscription.get("current_period_end"):
            current_period_end = (
                datetime.fromisoformat(
                    provider_subscription["current_period_end"].replace(
                        "Z", "+00:00")
                )
                if isinstance(provider_subscription["current_period_end"], str)
                else provider_subscription["current_period_end"]
            )

        subscription = await subscription_repo.create(
            customer_id=customer_id,
            plan_id=plan_id,
            provider=provider_name,
            provider_subscription_id=provider_subscription["provider_subscription_id"],
            status=provider_subscription["status"],
            quantity=quantity,
            current_period_start=current_period_start,
            current_period_end=current_period_end,
            cancel_at_period_end=provider_subscription.get(
                "cancel_at_period_end", False
            ),
            meta_info={
                **(meta_info or {}),
                "provider_data": {"items": provider_subscription.get("items", [])},
            },
        )

        # Publish event
        await self.event_publisher.publish_event(
            PaymentEvents.SUBSCRIPTION_CREATED,
            {
                "subscription_id": subscription.id,
                "customer_id": customer_id,
                "plan_id": plan_id,
                "provider": provider_name,
                "provider_subscription_id": provider_subscription[
                    "provider_subscription_id"
                ],
            },
        )

        # Return combined data
        return {
            "id": subscription.id,
            "customer_id": subscription.customer_id,
            "plan_id": subscription.plan_id,
            "provider": subscription.provider,
            "provider_subscription_id": subscription.provider_subscription_id,
            "status": subscription.status,
            "quantity": subscription.quantity,
            "current_period_start": subscription.current_period_start.isoformat(),
            "current_period_end": (
                subscription.current_period_end.isoformat()
                if subscription.current_period_end
                else None
            ),
            "cancel_at_period_end": subscription.cancel_at_period_end,
            "created_at": subscription.created_at.isoformat(),
        }

    async def get_subscription(self, subscription_id: str) -> Optional[Dict[str, Any]]:
        """
        Get subscription details.

        Args:
            subscription_id: Subscription ID

        Returns:
            Subscription data if found, None otherwise
        """
        if not self.db_session:
            raise RuntimeError("Database session not set")

        subscription_repo = SubscriptionRepository(self.db_session)
        subscription = await subscription_repo.get_with_plan(subscription_id)

        if not subscription:
            return None

        # Get provider subscription data
        provider_instance = self.get_provider(subscription.provider)
        try:
            provider_subscription = await provider_instance.retrieve_subscription(
                subscription.provider_subscription_id
            )
        except Exception as e:
            logger.error(f"Error retrieving provider subscription: {str(e)}")
            provider_subscription = {"error": str(e)}

        # Return combined data
        return {
            "id": subscription.id,
            "customer_id": subscription.customer_id,
            "plan_id": subscription.plan_id,
            "plan_name": subscription.plan.name if subscription.plan else None,
            "provider": subscription.provider,
            "provider_subscription_id": subscription.provider_subscription_id,
            "status": subscription.status,
            "quantity": subscription.quantity,
            "current_period_start": subscription.current_period_start.isoformat(),
            "current_period_end": (
                subscription.current_period_end.isoformat()
                if subscription.current_period_end
                else None
            ),
            "cancel_at_period_end": subscription.cancel_at_period_end,
            "created_at": subscription.created_at.isoformat(),
            "provider_data": provider_subscription,
        }

    async def cancel_subscription(
        self, subscription_id: str, cancel_at_period_end: bool = True
    ) -> Dict[str, Any]:
        """
        Cancel a subscription.

        Args:
            subscription_id: Subscription ID
            cancel_at_period_end: Whether to cancel at the end of the current period

        Returns:
            Updated subscription data
        """
        if not self.db_session:
            raise RuntimeError("Database session not set")

        subscription_repo = SubscriptionRepository(self.db_session)
        subscription = await subscription_repo.get_by_id(subscription_id)

        if not subscription:
            raise ValueError(f"Subscription not found: {subscription_id}")

        # Cancel subscription in provider
        provider_instance = self.get_provider(subscription.provider)
        provider_result = await provider_instance.cancel_subscription(
            subscription.provider_subscription_id, cancel_at_period_end
        )

        # Update subscription in database
        await subscription_repo.update(
            subscription_id,
            status="canceled" if not cancel_at_period_end else "active",
            cancel_at_period_end=(
                cancel_at_period_end if cancel_at_period_end else False
            ),
            canceled_at=datetime.utcnow() if not cancel_at_period_end else None,
        )

        # Publish event
        await self.event_publisher.publish_event(
            PaymentEvents.SUBSCRIPTION_CANCELED,
            {
                "subscription_id": subscription_id,
                "cancel_at_period_end": cancel_at_period_end,
                "canceled_at": datetime.utcnow().isoformat(),
            },
        )

        # Return updated subscription
        return await self.get_subscription(subscription_id)

    async def process_payment(
        self,
        customer_id: str,
        amount: float,
        currency: str,
        payment_method_id: Optional[str] = None,
        description: Optional[str] = None,
        meta_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Process a one-time payment.

        Args:
            customer_id: Customer ID
            amount: Payment amount
            currency: Currency code
            payment_method_id: Optional payment method ID
            description: Optional payment description
            meta_info: Optional payment meta_info

        Returns:
            Payment data
        """
        if not self.db_session:
            raise RuntimeError("Database session not set")

        customer_repo = CustomerRepository(self.db_session)
        customer = await customer_repo.get_with_provider_customers(customer_id)

        if not customer:
            raise ValueError(f"Customer not found: {customer_id}")

        # Determine provider
        provider_name = self.default_provider
        # If payment method ID is provided, extract provider from it
        if payment_method_id and ":" in payment_method_id:
            provider_name, payment_method_id = payment_method_id.split(":", 1)

        # Get provider customer
        provider_customer = await customer_repo.get_provider_customer(
            customer_id, provider_name
        )
        if not provider_customer:
            raise ValueError(
                f"Customer not found for provider {provider_name}")

        # Process payment with provider
        provider_instance = self.get_provider(provider_name)
        provider_payment = await provider_instance.process_payment(
            amount=amount,
            currency=currency,
            provider_customer_id=provider_customer.provider_customer_id,
            payment_method_id=payment_method_id,
            description=description,
            meta_info=meta_info,
        )

        # Create payment in database
        payment_repo = PaymentRepository(self.db_session)
        payment = await payment_repo.create(
            customer_id=customer_id,
            provider=provider_name,
            provider_payment_id=provider_payment["provider_payment_id"],
            amount=amount,
            currency=currency,
            status=provider_payment["status"],
            payment_method=payment_method_id,
            error_message=provider_payment.get("error_message"),
            meta_info={**(meta_info or {}), "description": description},
        )

        # Publish event
        event_type = (
            PaymentEvents.PAYMENT_SUCCEEDED
            if provider_payment["status"] == "COMPLETED"
            else PaymentEvents.PAYMENT_CREATED
        )
        await self.event_publisher.publish_event(
            event_type,
            {
                "payment_id": payment.id,
                "customer_id": customer_id,
                "amount": amount,
                "currency": currency,
                "status": provider_payment["status"],
                "provider": provider_name,
                "provider_payment_id": provider_payment["provider_payment_id"],
            },
        )

        # Return payment data
        return {
            "id": payment.id,
            "customer_id": payment.customer_id,
            "amount": payment.amount,
            "currency": payment.currency,
            "status": payment.status,
            "payment_method": payment.payment_method,
            "error_message": payment.error_message,
            "provider": payment.provider,
            "provider_payment_id": payment.provider_payment_id,
            "created_at": payment.created_at.isoformat(),
        }

    async def refund_payment(
        self, payment_id: str, amount: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Refund a payment, partially or fully.

        Args:
            payment_id: Payment ID
            amount: Optional refund amount (full refund if not specified)

        Returns:
            Updated payment data
        """
        if not self.db_session:
            raise RuntimeError("Database session not set")

        payment_repo = PaymentRepository(self.db_session)
        payment = await payment_repo.get_by_id(payment_id)

        if not payment:
            raise ValueError(f"Payment not found: {payment_id}")

        # Refund payment in provider
        provider_instance = self.get_provider(payment.provider)
        refund = await provider_instance.refund_payment(
            payment.provider_payment_id, amount
        )

        # Update payment in database
        refund_amount = amount or payment.amount
        await payment_repo.update(
            payment_id,
            status=(
                "refunded" if refund_amount >= payment.amount else "partially_refunded"
            ),
            refunded_amount=refund_amount,
        )

        # Publish event
        await self.event_publisher.publish_event(
            PaymentEvents.PAYMENT_REFUNDED,
            {
                "payment_id": payment_id,
                "refund_amount": refund_amount,
                "currency": payment.currency,
                "provider": payment.provider,
                "provider_refund_id": refund.get("provider_refund_id"),
            },
        )

        # Return updated payment
        payment = await payment_repo.get_by_id(payment_id)
        return {
            "id": payment.id,
            "customer_id": payment.customer_id,
            "amount": payment.amount,
            "refunded_amount": payment.refunded_amount,
            "currency": payment.currency,
            "status": payment.status,
            "provider": payment.provider,
            "provider_payment_id": payment.provider_payment_id,
            "created_at": payment.created_at.isoformat(),
        }

    async def record_usage(
        self,
        subscription_id: str,
        quantity: float,
        timestamp: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Record usage for a subscription.

        Args:
            subscription_id: Subscription ID
            quantity: Usage quantity
            timestamp: Optional usage timestamp
            description: Optional usage description

        Returns:
            Usage record data
        """
        if not self.db_session:
            raise RuntimeError("Database session not set")

        subscription_repo = SubscriptionRepository(self.db_session)
        subscription = await subscription_repo.get_by_id(subscription_id)

        if not subscription:
            raise ValueError(f"Subscription not found: {subscription_id}")

        # Record usage with provider
        provider_instance = self.get_provider(subscription.provider)
        usage = await provider_instance.record_usage(
            subscription.provider_subscription_id, quantity, timestamp
        )

        # Record usage in database
        from ..db.models import UsageRecord

        usage_repo = BaseRepository(UsageRecord, self.db_session)

        usage_record = await usage_repo.create(
            subscription_id=subscription_id,
            quantity=quantity,
            timestamp=(
                datetime.fromisoformat(
                    timestamp) if timestamp else datetime.utcnow()
            ),
            description=description,
        )

        # Publish event
        await self.event_publisher.publish_event(
            PaymentEvents.USAGE_RECORDED,
            {
                "subscription_id": subscription_id,
                "quantity": quantity,
                "timestamp": usage_record.timestamp.isoformat(),
                "description": description,
            },
        )

        # Return usage data
        return {
            "id": usage_record.id,
            "subscription_id": usage_record.subscription_id,
            "quantity": usage_record.quantity,
            "timestamp": usage_record.timestamp.isoformat(),
            "description": usage_record.description,
            "provider_usage_id": usage.get("id"),
        }

    async def handle_webhook(
        self, provider: str, payload: Any, signature: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Handle webhooks from payment providers.

        Args:
            provider: Provider name
            payload: Webhook payload
            signature: Optional webhook signature

        Returns:
            Processed webhook data
        """
        if provider not in self.providers:
            raise ValueError(f"Payment provider '{provider}' not found")

        provider_instance = self.get_provider(provider)

        # Process webhook with provider
        result = await provider_instance.webhook_handler(payload, signature)

        # Handle webhook based on standardized event type
        event_type = result.get("standardized_event_type")

        if event_type == "payment.succeeded":
            # Handle successful payment
            # Implementation depends on business logic
            pass
        elif event_type == "payment.failed":
            # Handle failed payment
            pass
        elif event_type == "subscription.created":
            # Handle subscription creation
            pass
        elif event_type == "subscription.updated":
            # Handle subscription update
            pass
        elif event_type == "subscription.canceled":
            # Handle subscription cancellation
            pass

        # Publish webhook event
        await self.event_publisher.publish_event(
            f"webhook.{provider}.{event_type}",
            {
                "provider": provider,
                "event_type": event_type,
                "data": result.get("data"),
            },
        )

        return result

    # Add the dependency injection function
    async def get_customer(self, customer_id: str) -> Optional[Dict[str, Any]]:
        """Get customer details by ID."""
        if hasattr(self, "customer_repo"):
            customer = await self.customer_repo.get_by_id(customer_id)
            if customer:
                provider_customers = await self.customer_repo.get_provider_customers(
                    customer_id
                )
                return {
                    "id": customer.id,
                    "email": customer.email,
                    "name": customer.name,
                    "created_at": customer.created_at.isoformat(),
                    "provider_customers": provider_customers,
                }
        return None


# Add the dependency injection function
def get_payment_service():
    """Dependency to get payment service instance."""
    # This is a placeholder - the actual implementation will be provided through DI
    raise NotImplementedError(
        "Payment service should be injected through FastAPI DI.")
