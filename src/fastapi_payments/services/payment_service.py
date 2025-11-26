from typing import Dict, Any, Optional, List
import logging
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from ..config.config_schema import PaymentConfig
from ..providers import get_provider
from ..messaging.publishers import PaymentEventPublisher, PaymentEvents
from ..db.repositories import (
    BaseRepository,
    CustomerRepository,
    PaymentRepository,
        PaymentMethodRepository,
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
            self.set_db_session(db_session)

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
        self.payment_method_repo = PaymentMethodRepository(session)
        # Sync job repository
        from ..db.repositories.sync_job_repository import SyncJobRepository

        self.sync_job_repo = SyncJobRepository(session)

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
        address: Optional[Dict[str, Any]] = None,
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
            email=email, name=name, meta_info=meta_info, address=address
        )

        # Save to database if session available
        if hasattr(self, "customer_repo"):
            # Persist address into the dedicated column. The repository will
            # detect and migrate any address embedded in meta_info if needed.
            customer = await self.customer_repo.create(
                email=email, name=name, meta_info=meta_info, address=address
            )

            # Link the provider's customer ID to our customer
            await self.customer_repo.add_provider_customer(
                customer_id=customer.id,
                provider=provider or self.default_provider,
                provider_customer_id=customer_data["provider_customer_id"],
            )

            # Return standardized customer data (include top-level address)
            return {
                "id": customer.id,
                "email": customer.email,
                "name": customer.name,
                "created_at": customer.created_at.isoformat(),
                "provider_customer_id": customer_data["provider_customer_id"],
                "meta_info": customer.meta_info,
                "address": customer.address,
            }
        else:
            # No database session, return the provider's response directly
            return {
                "id": f"cust_{hash(email) % 10000:04d}",  # Generate a fake ID
                **customer_data,
            }

    async def ensure_provider_customer(self, customer_id: str, provider: str) -> Dict[str, Any]:
        """Ensure the customer is registered with the requested provider."""
        if not self.db_session:
            raise RuntimeError("Database session not set")

        customer_repo = CustomerRepository(self.db_session)
        customer = await customer_repo.get_with_provider_customers(customer_id)
        if not customer:
            raise ValueError(f"Customer not found: {customer_id}")

        existing = next(
            (pc for pc in customer.provider_customers if pc.provider == provider),
            None,
        )
        if existing:
            return {
                "provider": existing.provider,
                "provider_customer_id": existing.provider_customer_id,
            }

        provider_instance = self.get_provider(provider)
        provider_payload = await provider_instance.create_customer(
            email=customer.email,
            name=customer.name,
            meta_info=customer.meta_info,
            address=customer.address,
        )
        provider_customer_id = provider_payload.get("provider_customer_id") or provider_payload.get("id")
        if not provider_customer_id:
            raise ValueError("Provider did not return a customer identifier")

        await customer_repo.add_provider_customer(
            customer_id=customer_id,
            provider=provider,
            provider_customer_id=provider_customer_id,
        )

        return {"provider": provider, "provider_customer_id": provider_customer_id}

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
            "address": customer.address,
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

    async def list_customers(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        search: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List customers stored in the service database."""

        if not self.db_session:
            raise RuntimeError("Database session not set")

        customer_repo = CustomerRepository(self.db_session)
        customers = await customer_repo.list(
            limit=limit,
            offset=offset,
            search=search,
            include_provider_customers=True,
        )

        results: List[Dict[str, Any]] = []
        for customer in customers:
            default_provider_link = next(
                (
                    pc
                    for pc in customer.provider_customers
                    if pc.provider == self.default_provider
                ),
                None,
            )
            results.append(
                {
                    "id": customer.id,
                    "email": customer.email,
                    "name": customer.name,
                    "meta_info": customer.meta_info,
                    "address": customer.address,
                    "created_at": customer.created_at.isoformat(),
                    "updated_at": customer.updated_at.isoformat()
                    if customer.updated_at
                    else None,
                    "provider_customer_id": (
                        default_provider_link.provider_customer_id
                        if default_provider_link
                        else None
                    ),
                    "provider_customers": [
                        {
                            "provider": pc.provider,
                            "provider_customer_id": pc.provider_customer_id,
                        }
                        for pc in customer.provider_customers
                    ],
                }
            )

        return results

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
        # If address provided, store into dedicated address column
        if "address" in kwargs and kwargs["address"] is not None:
            update_fields["address"] = kwargs["address"]

        for field in ["email", "name", "meta_info"]:
            if field in kwargs and field not in update_fields:
                update_fields[field] = kwargs[field]

        if update_fields:
            logger.debug(f"Updating customer {customer_id} with fields: {update_fields}")
            customer = await customer_repo.update(customer_id, **update_fields)

        # Update customer in providers
        for provider_customer in customer.provider_customers:
            provider_instance = self.get_provider(provider_customer.provider)
            try:
                # When updating providers, pass through any top-level fields.
                # If address is present, include it in the data payload as 'address'.
                provider_payload = dict(kwargs)
                await provider_instance.update_customer(
                    provider_customer.provider_customer_id, provider_payload
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

        # Persist payment method server-side if we have a session/repo
        if hasattr(self, "payment_method_repo"):
            # Normalize card metadata if present
            card = payment_method.get("card") or {}
            pm = await self.payment_method_repo.create(
                customer_id=customer_id,
                provider=provider_name,
                provider_payment_method_id=payment_method["payment_method_id"],
                mandate_id=payment_method.get("mandate_id"),
                is_default=payment_method.get("is_default", False),
                card_brand=card.get("brand"),
                card_last4=card.get("last4"),
                card_exp_month=card.get("exp_month"),
                card_exp_year=card.get("exp_year"),
                meta_info=payment_method.get("meta_info", {}),
            )

            # Replace returned payload with DB-backed values
            payment_method["stored_id"] = pm.id
            payment_method["is_default"] = pm.is_default
            # Ensure mandate_id (if provider returned one) is present
            if pm.mandate_id:
                payment_method["mandate_id"] = pm.mandate_id

        # Publish event
        await self.event_publisher.publish_event(
            PaymentEvents.PAYMENT_METHOD_CREATED,
            {
                "customer_id": customer_id,
                "provider": provider_name,
                "payment_method_id": payment_method["payment_method_id"],
            },
        )

        # Return payment method data (persisted if we have DB storage)
        result = {
            "id": payment_method.get("payment_method_id") or payment_method.get("stored_id"),
            "provider": provider_name,
            "type": payment_method.get("type"),
            "is_default": payment_method.get("is_default", False),
            "card": payment_method.get("card"),
            "created_at": datetime.utcnow().isoformat(),
        }
        # Include mandate_id if the provider returned it (e.g., from a SetupIntent)
        if payment_method.get("mandate_id"):
            result["mandate_id"] = payment_method.get("mandate_id")

        return result

    async def create_setup_intent(
        self, customer_id: str, provider: Optional[str] = None, usage: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a SetupIntent (or provider equivalent) for the given customer so
        a client-side flow (3DS) can be completed before saving a payment method.

        Returns a dict that includes `id` and `client_secret` keys when supported
        by the provider.
        """
        if not self.db_session:
            raise RuntimeError("Database session not set")

        provider_name = provider or self.default_provider
        customer_repo = CustomerRepository(self.db_session)

        provider_customer = await customer_repo.get_provider_customer(
            customer_id, provider_name
        )
        if not provider_customer:
            raise ValueError(
                f"Customer not found for provider {provider_name}"
            )

        provider_instance = self.get_provider(provider_name)
        result = await provider_instance.create_setup_intent(
            provider_customer.provider_customer_id, usage=usage
        )
        return result

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

        # Prefer returning server-side stored payment methods when available
        if hasattr(self, "payment_method_repo"):
            stored_methods = await self.payment_method_repo.list_for_customer(
                customer_id, provider=provider_name
            )
            return [
                {
                    "id": m.provider_payment_method_id,
                    "provider": m.provider,
                    "type": "card" if m.card_brand else "unknown",
                    "is_default": bool(m.is_default),
                    "card": {
                        "brand": m.card_brand,
                        "last4": m.card_last4,
                        "exp_month": m.card_exp_month,
                        "exp_year": m.card_exp_year,
                    }
                    if m.card_brand
                    else None,
                    "mandate_id": getattr(m, "mandate_id", None),
                }
                for m in stored_methods
            ]

        # Fallback: query provider directly when server storage isn't available
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
                "mandate_id": pm.get("mandate_id"),
            }
            for pm in payment_methods
        ]

    async def update_payment_method(
        self,
        customer_id: str,
        method_id: str,
        provider: Optional[str] = None,
        **fields: Any,
    ) -> Dict[str, Any]:
        """Update a stored payment method's attributes.

        Supported updates include setting is_default, or meta_info.
        """
        if not self.db_session:
            raise RuntimeError("Database session not set")

        pm_repo = self.payment_method_repo
        pm = await pm_repo.get_by_id(method_id)
        # If caller passed a provider_payment_method_id (not the DB id), try lookup
        if not pm:
            pm = await pm_repo.get_by_provider_method_id(provider, method_id)
        if not pm or pm.customer_id != customer_id:
            raise ValueError("Payment method not found for customer")

        # Handle set_default specially: update provider and DB
        if fields.get("is_default"):
            # Use repository helper to mark default
            await pm_repo.set_default(customer_id, method_id)

            # If provider supports setting default at customer-level, attempt it
            try:
                provider_instance = self.get_provider(provider or pm.provider)
                # update the provider customer's invoice_settings.default_payment_method
                # Find provider_customer link
                customer_repo = CustomerRepository(self.db_session)
                provider_customer = await customer_repo.get_provider_customer(
                    customer_id, provider or pm.provider
                )
                if provider_customer:
                    await provider_instance.update_customer(
                        provider_customer.provider_customer_id,
                        {"invoice_settings": {"default_payment_method": pm.provider_payment_method_id}},
                    )
            except Exception:
                # Provider may not support or we don't want failures to block; log and continue
                logger.exception("Failed to set provider-side default payment method")

        # Update any DB-stored meta or card fields
        update_fields = {k: v for k, v in fields.items() if k != "is_default"}
        if update_fields:
            updated = await pm_repo.update(method_id, **update_fields)
            pm = updated

        return {
            "id": pm.provider_payment_method_id,
            "provider": pm.provider,
            "is_default": bool(pm.is_default),
            "card": {
                "brand": pm.card_brand,
                "last4": pm.card_last4,
                "exp_month": pm.card_exp_month,
                "exp_year": pm.card_exp_year,
            }
            if pm.card_brand
            else None,
            "mandate_id": getattr(pm, "mandate_id", None),
        }

    async def delete_payment_method(
        self, customer_id: str, method_id: str, provider: Optional[str] = None
    ) -> Dict[str, Any]:
        """Delete (detach) a stored payment method both in provider (if supported) and DB."""
        if not self.db_session:
            raise RuntimeError("Database session not set")

        pm_repo = self.payment_method_repo
        pm = await pm_repo.get_by_id(method_id)
        if not pm:
            pm = await pm_repo.get_by_provider_method_id(provider, method_id)
        if not pm or pm.customer_id != customer_id:
            raise ValueError("Payment method not found for customer")

        provider_name = provider or pm.provider
        # Try to delete/detach in provider
        try:
            provider_instance = self.get_provider(provider_name)
            if hasattr(provider_instance, "delete_payment_method"):
                await provider_instance.delete_payment_method(pm.provider_payment_method_id)
        except Exception:
            logger.exception("Error deleting payment method at provider; continuing to remove DB record")

        # Remove from DB
        deleted = await pm_repo.delete(method_id)
        # Publish event
        await self.event_publisher.publish_event(
            PaymentEvents.PAYMENT_METHOD_DELETED,
            {"customer_id": customer_id, "provider": provider_name, "payment_method_id": method_id},
        )

        return {"deleted": bool(deleted), "id": method_id}

    async def set_default_payment_method(
        self, customer_id: str, method_id: str, provider: Optional[str] = None
    ) -> Dict[str, Any]:
        """Mark a stored payment method as the default for the customer.

        Updates both DB (via repository.set_default) and attempts to update the provider's
        customer default payment settings where supported.
        """
        if not self.db_session:
            raise RuntimeError("Database session not set")

        pm_repo = self.payment_method_repo
        pm = await pm_repo.get_by_id(method_id)
        if not pm:
            pm = await pm_repo.get_by_provider_method_id(provider, method_id)
        if not pm or pm.customer_id != customer_id:
            raise ValueError("Payment method not found for customer")

        # Set DB default
        updated = await pm_repo.set_default(customer_id, method_id)

        # Set default on provider (customer invoice settings) if possible
        try:
            provider_instance = self.get_provider(provider or pm.provider)
            customer_repo = CustomerRepository(self.db_session)
            provider_customer = await customer_repo.get_provider_customer(
                customer_id, provider or pm.provider
            )
            if provider_customer:
                await provider_instance.update_customer(
                    provider_customer.provider_customer_id,
                    {"invoice_settings": {"default_payment_method": pm.provider_payment_method_id}},
                )
        except Exception:
            logger.exception("Failed to set provider-side default payment method")

        return {
            "id": updated.provider_payment_method_id,
            "is_default": bool(updated.is_default),
            "provider": updated.provider,
        }

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

    async def list_products(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Return products stored in the local database."""

        if not self.db_session:
            raise RuntimeError("Database session not set")

        products = await self.product_repo.list(limit=limit, offset=offset)
        results: List[Dict[str, Any]] = []
        for product in products:
            meta_info = product.meta_info or {}
            results.append(
                {
                    "id": product.id,
                    "name": product.name,
                    "description": product.description,
                    "active": product.active,
                    "provider_product_id": meta_info.get("provider_product_id", ""),
                    "provider": meta_info.get("provider", self.default_provider),
                    "created_at": product.created_at.isoformat(),
                    "meta_info": meta_info or None,
                }
            )
        return results

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

    async def list_plans(
        self,
        *,
        product_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Return plans, optionally filtered by product."""

        if not self.db_session:
            raise RuntimeError("Database session not set")

        plans = await self.plan_repo.list(
            product_id=product_id, limit=limit, offset=offset
        )

        results: List[Dict[str, Any]] = []
        for plan in plans:
            meta_info = plan.meta_info or {}
            pricing_model = (
                plan.pricing_model.value
                if hasattr(plan.pricing_model, "value")
                else plan.pricing_model
            )
            results.append(
                {
                    "id": plan.id,
                    "product_id": plan.product_id,
                    "name": plan.name,
                    "description": plan.description,
                    "pricing_model": pricing_model,
                    "amount": plan.amount,
                    "currency": plan.currency,
                    "billing_interval": plan.billing_interval,
                    "billing_interval_count": plan.billing_interval_count,
                    "trial_period_days": plan.trial_period_days,
                    "provider": meta_info.get("provider", self.default_provider),
                    "provider_price_id": meta_info.get("provider_price_id", ""),
                    "created_at": plan.created_at.isoformat(),
                    "meta_info": meta_info or None,
                }
            )

        return results

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

    async def list_subscriptions(
        self,
        *,
        customer_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Return subscriptions filtered by optional criteria."""

        if not self.db_session:
            raise RuntimeError("Database session not set")

        subscriptions = await self.subscription_repo.list(
            customer_id=customer_id,
            status=status,
            limit=limit,
            offset=offset,
            include_plan=True,
        )

        results: List[Dict[str, Any]] = []
        for subscription in subscriptions:
            provider_data = None
            if subscription.meta_info:
                provider_data = subscription.meta_info.get("provider_data")
            results.append(
                {
                    "id": subscription.id,
                    "customer_id": subscription.customer_id,
                    "plan_id": subscription.plan_id,
                    "plan_name": subscription.plan.name if subscription.plan else None,
                    "provider": subscription.provider,
                    "provider_subscription_id": subscription.provider_subscription_id,
                    "status": subscription.status,
                    "quantity": subscription.quantity,
                    "current_period_start": subscription.current_period_start.isoformat()
                    if subscription.current_period_start
                    else None,
                    "current_period_end": subscription.current_period_end.isoformat()
                    if subscription.current_period_end
                    else None,
                    "cancel_at_period_end": subscription.cancel_at_period_end,
                    "created_at": subscription.created_at.isoformat(),
                    "provider_data": provider_data,
                }
            )

        return results

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
        mandate_id: Optional[str] = None,
        provider: Optional[str] = None,
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
        provider_name = provider or self.default_provider
        # If provider not explicitly requested and payment method encodes it, respect that
        if not provider and payment_method_id and ":" in payment_method_id:
            provider_name, payment_method_id = payment_method_id.split(":", 1)

        # Get provider customer
        provider_customer = await customer_repo.get_provider_customer(
            customer_id, provider_name
        )
        if not provider_customer:
            raise ValueError(
                f"Customer not found for provider {provider_name}")

        # Enrich meta info with customer context for providers that need it
        request_meta_info = dict(meta_info or {})
        provider_meta_payload = dict(request_meta_info)
        provider_meta_payload["customer_context"] = {
            "id": customer.id,
            "email": customer.email,
            "name": customer.name,
            "meta_info": customer.meta_info or {},
        }

        # Process payment with provider
        provider_instance = self.get_provider(provider_name)
        provider_payment = await provider_instance.process_payment(
            amount=amount,
            currency=currency,
            provider_customer_id=provider_customer.provider_customer_id,
            payment_method_id=payment_method_id,
            description=description,
            mandate_id=mandate_id,
            meta_info=provider_meta_payload,
        )

        combined_meta_info = dict(request_meta_info)
        if provider_payment.get("meta_info"):
            combined_meta_info.setdefault("provider_data", {})
            combined_meta_info["provider_data"][provider_name] = provider_payment["meta_info"]
        stored_meta_info = combined_meta_info or None

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
            meta_info=(
                {**stored_meta_info, "description": description}
                if stored_meta_info
                else ({"description": description} if description else None)
            ),
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
            "meta_info": payment.meta_info,
        }

    async def sync_resources(
        self,
        resources: Optional[List[str]] = None,
        provider: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Synchronize local DB state with provider(s).

        This is best-effort: for each requested resource we attempt to fetch
        authoritative data from the configured provider(s) and update local
        rows where possible. If a provider does not implement the expected
        retrieval method for a resource, the resource is skipped for that
        provider.

        Args:
            resources: list of resource names to sync (customers, products,
                plans, payments, subscriptions, payment_methods). If None,
                all supported resources are synced.
            provider: optional provider name to limit sync to one provider.
            filters: resource-specific filters e.g. {'customer_id': '...'}
            limit/offset: pagination for resource listing.

        Returns:
            A dict summarizing how many items were examined/updated and any
            errors encountered for each resource.
        """
        if not self.db_session:
            raise RuntimeError("Database session not set")

        supported = [
            "customers",
            "products",
            "plans",
            "payments",
            "subscriptions",
            "payment_methods",
        ]

        to_sync = set(resources or supported)
        result: Dict[str, Any] = {r: {"synced": 0, "updated": 0, "created": 0, "errors": []} for r in to_sync if r in supported}
        filters = filters or {}

        # CUSTOMERS
        if "customers" in to_sync:
            try:
                cust_repo = CustomerRepository(self.db_session)
                if filters.get("customer_id"):
                    customers = [await cust_repo.get_with_provider_customers(filters["customer_id"])]
                else:
                    customers = await cust_repo.list(limit=limit, offset=offset, include_provider_customers=True)

                for customer in customers:
                    if not customer:
                        continue
                    result["customers"]["synced"] += 1
                    # For each provider link, try to retrieve provider data
                    for pc in customer.provider_customers:
                        if provider and pc.provider != provider:
                            continue
                        provider_instance = self.get_provider(pc.provider)
                        retrieve = getattr(provider_instance, "retrieve_customer", None)
                        if not callable(retrieve):
                            continue
                        try:
                            pdata = await retrieve(pc.provider_customer_id)
                            # Persist provider data into customer.meta_info.provider_data
                            meta = dict(customer.meta_info or {})
                            provider_map = dict(meta.get("provider_data") or {})
                            provider_map[pc.provider] = pdata
                            meta["provider_data"] = provider_map
                            await cust_repo.update(customer.id, meta_info=meta)
                            result["customers"]["updated"] += 1
                        except Exception as e:
                            result["customers"]["errors"].append(str(e))
            except Exception as e:
                result["customers"]["errors"].append(str(e))

        # PRODUCTS
        if "products" in to_sync:
            try:
                prod_repo = ProductRepository(self.db_session)
                if filters.get("product_id"):
                    prods = [await prod_repo.get_by_id(filters["product_id"])]
                else:
                    prods = await prod_repo.list(limit=limit, offset=offset)

                for p in prods:
                    if not p:
                        continue
                    result["products"]["synced"] += 1
                    meta = p.meta_info or {}
                    prov = provider or meta.get("provider")
                    prov_pid = meta.get("provider_product_id")
                    if not prov or not prov_pid:
                        continue
                    provider_instance = self.get_provider(prov)
                    retrieve = getattr(provider_instance, "retrieve_product", None)
                    if not callable(retrieve):
                        # provider doesn't expose retrieve_product: skip
                        continue
                    try:
                        pdata = await retrieve(prov_pid)
                        provider_map = dict(meta.get("provider_data") or {})
                        provider_map[prov] = pdata
                        meta["provider_data"] = provider_map
                        await prod_repo.update(p.id, meta_info=meta)
                        result["products"]["updated"] += 1
                    except Exception as e:
                        result["products"]["errors"].append(str(e))
            except Exception as e:
                result["products"]["errors"].append(str(e))

        # PLANS
        if "plans" in to_sync:
            try:
                plan_repo = PlanRepository(self.db_session)
                if filters.get("plan_id"):
                    plans = [await plan_repo.get_by_id(filters["plan_id"])]
                else:
                    plans = await plan_repo.list(limit=limit, offset=offset)

                for pl in plans:
                    if not pl:
                        continue
                    result["plans"]["synced"] += 1
                    meta = pl.meta_info or {}
                    prov = provider or meta.get("provider")
                    prov_price_id = meta.get("provider_price_id")
                    if not prov or not prov_price_id:
                        continue
                    provider_instance = self.get_provider(prov)
                    # Try a couple of possible method names
                    retrieve = getattr(provider_instance, "retrieve_price", None) or getattr(provider_instance, "retrieve_plan", None)
                    if not callable(retrieve):
                        continue
                    try:
                        pdata = await retrieve(prov_price_id)
                        provider_map = dict(meta.get("provider_data") or {})
                        provider_map[prov] = pdata
                        meta["provider_data"] = provider_map
                        await plan_repo.update(pl.id, meta_info=meta)
                        result["plans"]["updated"] += 1
                    except Exception as e:
                        result["plans"]["errors"].append(str(e))
            except Exception as e:
                result["plans"]["errors"].append(str(e))

        # SUBSCRIPTIONS
        if "subscriptions" in to_sync:
            try:
                sub_repo = SubscriptionRepository(self.db_session)
                if filters.get("subscription_id"):
                    subs = [await sub_repo.get_by_id(filters["subscription_id"])]
                else:
                    subs = await sub_repo.list(limit=limit, offset=offset, include_plan=True)

                for s in subs:
                    if not s:
                        continue
                    result["subscriptions"]["synced"] += 1
                    if provider and s.provider != provider:
                        continue
                    provider_instance = self.get_provider(s.provider)
                    retrieve = getattr(provider_instance, "retrieve_subscription", None)
                    if not callable(retrieve):
                        continue
                    try:
                        pdata = await retrieve(s.provider_subscription_id)
                        # Update local subscription fields where appropriate
                        update_fields: Dict[str, Any] = {}
                        status = pdata.get("status")
                        if status:
                            update_fields["status"] = status
                        cps = pdata.get("current_period_start") or pdata.get("current_period_start_iso")
                        cpe = pdata.get("current_period_end") or pdata.get("current_period_end_iso")
                        if cps:
                            try:
                                update_fields["current_period_start"] = (
                                    datetime.fromisoformat(cps.replace("Z", "+00:00"))
                                    if isinstance(cps, str)
                                    else cps
                                )
                            except Exception:
                                pass
                        if cpe:
                            try:
                                update_fields["current_period_end"] = (
                                    datetime.fromisoformat(cpe.replace("Z", "+00:00"))
                                    if isinstance(cpe, str)
                                    else cpe
                                )
                            except Exception:
                                pass
                        if "cancel_at_period_end" in pdata:
                            update_fields["cancel_at_period_end"] = pdata.get("cancel_at_period_end")
                        if update_fields:
                            await sub_repo.update(s.id, **update_fields)
                            result["subscriptions"]["updated"] += 1
                    except Exception as e:
                        result["subscriptions"]["errors"].append(str(e))
            except Exception as e:
                result["subscriptions"]["errors"].append(str(e))

        # PAYMENTS
        if "payments" in to_sync:
            try:
                pay_repo = PaymentRepository(self.db_session)
                if filters.get("payment_id"):
                    pays = [await pay_repo.get_by_id(filters["payment_id"])]
                else:
                    pays = await pay_repo.list(limit=limit, offset=offset)

                for p in pays:
                    if not p:
                        continue
                    result["payments"]["synced"] += 1
                    if provider and p.provider != provider:
                        continue
                    provider_instance = self.get_provider(p.provider)
                    retrieve = getattr(provider_instance, "retrieve_payment", None)
                    if not callable(retrieve):
                        continue
                    try:
                        pdata = await retrieve(p.provider_payment_id)
                        update_fields = {}
                        if pdata.get("status"):
                            update_fields["status"] = pdata.get("status")
                        if pdata.get("meta_info"):
                            update_fields["meta_info"] = {**(p.meta_info or {}), "provider_data": {p.provider: pdata.get("meta_info")}}
                        if update_fields:
                            await pay_repo.update(p.id, **update_fields)
                            result["payments"]["updated"] += 1
                    except Exception as e:
                        result["payments"]["errors"].append(str(e))
            except Exception as e:
                result["payments"]["errors"].append(str(e))

        # PAYMENT METHODS (attempt reconcile provider-side saved methods)
        if "payment_methods" in to_sync:
            try:
                cust_repo = CustomerRepository(self.db_session)
                pm_repo = PaymentMethodRepository(self.db_session)
                # If a customer_id filter is present we only fetch for that customer
                if filters.get("customer_id"):
                    customers = [await cust_repo.get_with_provider_customers(filters["customer_id"])]
                else:
                    customers = await cust_repo.list(limit=limit, offset=offset, include_provider_customers=True)

                for customer in customers:
                    if not customer:
                        continue
                    # For each provider-link, fetch provider's payment methods
                    for pc in customer.provider_customers:
                        if provider and pc.provider != provider:
                            continue
                        prov = pc.provider
                        provider_instance = self.get_provider(prov)
                        list_pm = getattr(provider_instance, "list_payment_methods", None)
                        if not callable(list_pm):
                            continue
                        try:
                            pms = await list_pm(pc.provider_customer_id)
                            result["payment_methods"]["synced"] += len(pms)
                            for pm in pms:
                                # pm should include payment_method_id and card data
                                pid = pm.get("payment_method_id")
                                if not pid:
                                    continue
                                existing = await pm_repo.get_by_provider_method_id(prov, pid)
                                if existing:
                                    # update metadata
                                    await pm_repo.update(existing.id, meta_info={**(existing.meta_info or {}), "provider_data": pm})
                                    result["payment_methods"]["updated"] += 1
                                else:
                                    # create new DB-backed method
                                    card = pm.get("card") or {}
                                    await pm_repo.create(
                                        customer_id=customer.id,
                                        provider=prov,
                                        provider_payment_method_id=pid,
                                        mandate_id=pm.get("mandate_id"),
                                        is_default=pm.get("is_default", False),
                                        card_brand=card.get("brand"),
                                        card_last4=card.get("last4"),
                                        card_exp_month=card.get("exp_month"),
                                        card_exp_year=card.get("exp_year"),
                                        meta_info={"provider_data": pm},
                                    )
                                    result["payment_methods"]["created"] += 1
                        except Exception as e:
                            result["payment_methods"]["errors"].append(str(e))
            except Exception as e:
                result["payment_methods"]["errors"].append(str(e))

        # Convert result payload items into simpler dicts
        # (ensure errors lists exist)
        for k, v in result.items():
            if "errors" not in v or v["errors"] is None:
                v["errors"] = []

        return {"summary": result}

    async def create_sync_job(self, resources: Optional[List[str]] = None, provider: Optional[str] = None, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a SyncJob record and return its basic details.

        Actual work is performed by execute_sync_job which is expected to be
        scheduled as a background task by the API layer.
        """
        if not self.db_session:
            raise RuntimeError("Database session not set")

        job = await self.sync_job_repo.create(resources=resources, provider=provider, filters=filters)
        return {"id": job.id, "status": job.status, "created_at": job.created_at.isoformat(), "updated_at": job.updated_at.isoformat()}

    async def execute_sync_job(self, job_id: str):
        """Run sync_resources for a previously created job and persist results.

        This method will set job status to 'running', invoke sync_resources,
        and finally store the result and mark job 'completed' or 'failed'.
        """
        # For background execution we cannot rely on the request-scoped DB
        # session. Create a fresh session from the repositories' sessionmaker
        # and run the job inside it.
        from ..db.repositories import _sessionmaker  # type: ignore

        if _sessionmaker is None:
            raise RuntimeError("Database not initialized; cannot run job")

        async with _sessionmaker() as session:
            # Use a fresh PaymentService instance tied to this session so
            # repositories use a valid session for the duration of the job.
            svc = PaymentService(self.config, self.event_publisher, session)

            job = await svc.sync_job_repo.get_by_id(job_id)
            if not job:
                raise ValueError(f"Sync job not found: {job_id}")

            # mark running
            await svc.sync_job_repo.update_status(job_id, "running")

            try:
                res = await svc.sync_resources(resources=job.resources, provider=job.provider, filters=job.filters)
                await svc.sync_job_repo.update_status(job_id, "completed", result=res)
            except Exception as e:
                await svc.sync_job_repo.update_status(job_id, "failed", result={"error": str(e)})
                raise

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

    async def list_payments(
        self,
        *,
        customer_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Return payments filtered by optional criteria."""

        if not self.db_session:
            raise RuntimeError("Database session not set")

        payments = await self.payment_repo.list(
            customer_id=customer_id,
            status=status,
            limit=limit,
            offset=offset,
            include_customer=True,
        )

        results: List[Dict[str, Any]] = []
        for payment in payments:
            status_value = (
                payment.status.value if hasattr(payment.status, "value") else payment.status
            )
            results.append(
                {
                    "id": payment.id,
                    "customer_id": payment.customer_id,
                    "amount": payment.amount,
                    "refunded_amount": payment.refunded_amount,
                    "currency": payment.currency,
                    "status": status_value,
                    "payment_method": payment.payment_method,
                    "error_message": payment.error_message,
                    "provider": payment.provider,
                    "provider_payment_id": payment.provider_payment_id,
                    "created_at": payment.created_at.isoformat(),
                    "meta_info": payment.meta_info,
                }
            )

        return results

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
def get_payment_service():
    """Dependency to get payment service instance."""
    # This is a placeholder - the actual implementation will be provided through DI
    raise NotImplementedError(
        "Payment service should be injected through FastAPI DI.")
