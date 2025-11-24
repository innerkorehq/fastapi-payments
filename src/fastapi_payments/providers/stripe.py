"""Stripe payment provider implementation."""

import asyncio
import inspect
import json
import logging
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional

from .base import PaymentProvider

logger = logging.getLogger(__name__)


class StripeProvider(PaymentProvider):
    """Stripe payment provider backed by the official SDK."""

    ZERO_DECIMAL_CURRENCIES = {
        "BIF",
        "CLP",
        "DJF",
        "GNF",
        "JPY",
        "KMF",
        "KRW",
        "MGA",
        "PYG",
        "RWF",
        "UGX",
        "VND",
        "VUV",
        "XAF",
        "XOF",
        "XPF",
    }

    EVENT_TYPE_MAP = {
        "payment_intent.succeeded": "payment.succeeded",
        "payment_intent.payment_failed": "payment.failed",
        "invoice.payment_failed": "invoice.payment_failed",
        "invoice.payment_succeeded": "invoice.payment_succeeded",
        "customer.subscription.created": "subscription.created",
        "customer.subscription.updated": "subscription.updated",
        "customer.subscription.deleted": "subscription.canceled",
        "charge.refunded": "payment.refunded",
    }

    def initialize(self):
        """Initialize Stripe with configuration."""
        self.api_key = self.config.api_key
        self.webhook_secret = getattr(self.config, "webhook_secret", None)
        self.sandbox_mode = getattr(self.config, "sandbox_mode", True)
        additional_settings = getattr(self.config, "additional_settings", {}) or {}
        self.api_version = additional_settings.get("api_version", "2023-10-16")
        self.max_network_retries = additional_settings.get("max_network_retries")
        self.default_payment_method_type = additional_settings.get(
            "payment_method_type", "card"
        )
        self.default_usage_action = additional_settings.get("usage_action", "increment")
        self.default_payment_behavior = additional_settings.get(
            "payment_behavior", "allow_incomplete"
        )

        logger.info(
            "Initialized Stripe provider with API version %s", self.api_version
        )

        self.stripe = None
        self.stripe_error = None
        self._run_stripe_calls_in_thread = True

        try:
            import stripe

            stripe.api_key = self.api_key
            stripe.api_version = self.api_version
            if self.max_network_retries is not None:
                stripe.max_network_retries = self.max_network_retries

            self.stripe = stripe
            self.stripe_error = getattr(stripe, "error", None)
            logger.info("Using real Stripe SDK")
        except ImportError:
            logger.warning(
                "Stripe package not installed. Install with 'pip install stripe'"
            )

    async def create_customer(
        self,
        email: str,
        name: Optional[str] = None,
        meta_info: Optional[Dict[str, Any]] = None,
        address: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a customer in Stripe."""
        metadata = self._prepare_metadata(meta_info)
        params: Dict[str, Any] = {"email": email, "name": name}
        if metadata:
            params["metadata"] = metadata
        # include address if provided (Stripe expects an address dict)
        if address:
            # Accept either dotted-field or direct dict and forward to Stripe
            params["address"] = {
                k: v for k, v in {
                    "line1": address.get("line1") if isinstance(address, dict) else None,
                    "line2": address.get("line2") if isinstance(address, dict) else None,
                    "city": address.get("city") if isinstance(address, dict) else None,
                    "state": address.get("state") if isinstance(address, dict) else None,
                    "postal_code": address.get("postal_code") if isinstance(address, dict) else None,
                    "country": address.get("country") if isinstance(address, dict) else None,
                }.items()
                if v
            }
        customer = await self._call_stripe(self.stripe.Customer.create, **params)
        return self._format_customer(customer)

    async def retrieve_customer(self, provider_customer_id: str) -> Dict[str, Any]:
        """Retrieve customer from Stripe."""
        customer = await self._call_stripe(
            self.stripe.Customer.retrieve, provider_customer_id
        )
        return self._format_customer(customer)

    async def update_customer(
        self, provider_customer_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update customer data in Stripe."""
        payload: Dict[str, Any] = {}
        if "email" in data:
            payload["email"] = data["email"]
        if "name" in data:
            payload["name"] = data["name"]
        if "address" in data and data.get("address"):
            addr = data.get("address")
            payload["address"] = {
                k: v for k, v in {
                    "line1": addr.get("line1") if isinstance(addr, dict) else None,
                    "line2": addr.get("line2") if isinstance(addr, dict) else None,
                    "city": addr.get("city") if isinstance(addr, dict) else None,
                    "state": addr.get("state") if isinstance(addr, dict) else None,
                    "postal_code": addr.get("postal_code") if isinstance(addr, dict) else None,
                    "country": addr.get("country") if isinstance(addr, dict) else None,
                }.items()
                if v
            }
        if data.get("meta_info"):
            payload["metadata"] = self._prepare_metadata(data["meta_info"])

        customer = await self._call_stripe(
            self.stripe.Customer.modify, provider_customer_id, **payload
        )
        normalized = self._format_customer(customer)
        normalized["updated_at"] = datetime.now(timezone.utc).isoformat()
        return normalized

    async def delete_customer(self, provider_customer_id: str) -> Dict[str, Any]:
        """Delete a customer from Stripe."""
        response = await self._call_stripe(
            self.stripe.Customer.delete, provider_customer_id
        )
        deleted = bool(self._to_plain_dict(response).get("deleted", False))
        return {"deleted": deleted, "provider_customer_id": provider_customer_id}

    async def create_payment_method(
        self, provider_customer_id: str, payment_details: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a payment method in Stripe and attach it to the customer."""
        params = dict(payment_details)
        params.setdefault("type", self.default_payment_method_type)
        attach_behavior = params.pop("set_default", True)
        
        # Check if payment_method_id is provided (for attaching existing payment method)
        payment_method_id = params.pop("payment_method_id", None)
        
        if payment_method_id:
            # If a payment method id is supplied, prefer retrieving it first
            # and only attach if it's not already attached to the correct
            # customer. This handles cases where a SetupIntent has already
            # attached the payment method (eg. India 3DS flows).
            try:
                pm = await self._call_stripe(
                    self.stripe.PaymentMethod.retrieve, payment_method_id
                )
                pm_data = self._to_plain_dict(pm)
                current_customer = pm_data.get("customer")
                if not current_customer:
                    payment_method = await self._call_stripe(
                        self.stripe.PaymentMethod.attach,
                        payment_method_id,
                        customer=provider_customer_id,
                    )
                elif current_customer != provider_customer_id:
                    # Attempt to attach to the provided customer; Stripe may
                    # raise if cross-customer attachments are not allowed.
                    payment_method = await self._call_stripe(
                        self.stripe.PaymentMethod.attach,
                        payment_method_id,
                        customer=provider_customer_id,
                    )
                else:
                    payment_method = pm
            except Exception:
                # Fall back to attempting an attach which will raise a helpful
                # Stripe error if it can't be attached.
                payment_method = await self._call_stripe(
                    self.stripe.PaymentMethod.attach,
                    payment_method_id,
                    customer=provider_customer_id,
                )
        else:
            # Create new payment method. Only forward known, allowed keys to
            # Stripe when creating a PaymentMethod to avoid passing unknown
            # parameters (e.g. payment_method_id) which cause Stripe API errors.
            token = params.pop("token", None)

            allowed_create_keys = {"type", "card", "billing_details", "metadata"}
            create_params = {k: v for k, v in params.items() if k in allowed_create_keys}

            # If a token was supplied, prefer creating using the token wrapped
            # inside the card payload (this keeps compatibility with token-based
            # clients). If token is present and card isn't already passed, add it.
            if token and "card" not in create_params:
                create_params["card"] = {"token": token}

            payment_method = await self._call_stripe(
                self.stripe.PaymentMethod.create, **create_params
            )

            # Attach the newly created payment method to the customer.
            await self._call_stripe(
                self.stripe.PaymentMethod.attach, payment_method["id"],
                customer=provider_customer_id,
            )

        if attach_behavior:
            await self._call_stripe(
                self.stripe.Customer.modify,
                provider_customer_id,
                invoice_settings={"default_payment_method": payment_method["id"]},
            )

        # If a setup_intent_id was provided, try to retrieve the SetupIntent
        # and see if a mandate was created as part of the setup flow.
        mandate_id = None
        setup_intent_id = payment_details.get("setup_intent_id") if isinstance(payment_details, dict) else None
        if setup_intent_id:
            try:
                si = await self._call_stripe(self.stripe.SetupIntent.retrieve, setup_intent_id)
                si_data = self._to_plain_dict(si)
                # SetupIntent may include a top-level 'mandate' or nested fields depending on API version
                m = si_data.get("mandate") or si_data.get("latest_attempt", {}).get("mandate")
                if isinstance(m, dict):
                    mandate_id = m.get("id")
                elif isinstance(m, str):
                    mandate_id = m
            except Exception:
                # Ignore — retrieving SetupIntent is best-effort
                mandate_id = None

        formatted = self._format_payment_method(payment_method)
        if mandate_id:
            formatted["mandate_id"] = mandate_id

        return formatted

    async def create_setup_intent(
        self, provider_customer_id: str, usage: Optional[str] = None, **kwargs
    ) -> Dict[str, Any]:
        """Create a Stripe SetupIntent to be confirmed client-side by the
        browser. Returns the SetupIntent id and client_secret so the client
        can call stripe.confirmCardSetup(...) to complete 3DS flows required
        in certain regions (e.g. India).
        """
        params = {
            "customer": provider_customer_id,
            "payment_method_types": [self.default_payment_method_type],
        }
        if usage:
            params["usage"] = usage
        setup_intent = await self._call_stripe(self.stripe.SetupIntent.create, **params)
        si = self._to_plain_dict(setup_intent)
        return {"id": si.get("id"), "client_secret": si.get("client_secret")}

    async def list_payment_methods(
        self, provider_customer_id: str
    ) -> List[Dict[str, Any]]:
        """List payment methods for a customer in Stripe."""
        payment_method_type = self.default_payment_method_type
        response = await self._call_stripe(
            self.stripe.PaymentMethod.list,
            customer=provider_customer_id,
            type=payment_method_type,
        )
        items = self._to_plain_dict(response).get("data", [])
        return [self._format_payment_method(pm) for pm in items]

    async def delete_payment_method(self, payment_method_id: str) -> Dict[str, Any]:
        """Detach a payment method from Stripe."""
        response = await self._call_stripe(
            self.stripe.PaymentMethod.detach, payment_method_id
        )
        data = self._to_plain_dict(response)
        deleted = data.get("customer") is None
        return {"deleted": deleted, "payment_method_id": payment_method_id}

    async def create_product(
        self,
        name: str,
        description: Optional[str] = None,
        meta_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a product in Stripe."""
        metadata = self._prepare_metadata(meta_info)
        params: Dict[str, Any] = {"name": name, "description": description, "active": True}
        if metadata:
            params["metadata"] = metadata
        product = await self._call_stripe(self.stripe.Product.create, **params)
        return self._format_product(product)

    async def create_price(
        self,
        product_id: str,
        amount: float,
        currency: str,
        interval: Optional[str] = None,
        interval_count: Optional[int] = None,
        meta_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a price in Stripe."""
        params: Dict[str, Any] = {
            "product": product_id,
            "unit_amount": self._to_stripe_amount(amount, currency),
            "currency": currency.lower(),
        }
        metadata = self._prepare_metadata(meta_info)
        if metadata:
            params["metadata"] = metadata
        if interval:
            params["recurring"] = {
                "interval": interval,
                "interval_count": interval_count or 1,
            }

        price = await self._call_stripe(self.stripe.Price.create, **params)
        return self._format_price(price)

    async def create_subscription(
        self,
        provider_customer_id: str,
        price_id: str,
        quantity: int = 1,
        trial_period_days: Optional[int] = None,
        meta_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a subscription in Stripe."""
        params: Dict[str, Any] = {
            "customer": provider_customer_id,
            "items": [{"price": price_id, "quantity": quantity}],
            "payment_behavior": self.default_payment_behavior,
            "expand": ["latest_invoice.payment_intent"],
        }
        metadata = self._prepare_metadata(meta_info)
        if metadata:
            params["metadata"] = metadata
        if trial_period_days:
            params["trial_period_days"] = trial_period_days

        subscription = await self._call_stripe(
            self.stripe.Subscription.create, **params
        )
        return self._format_subscription(subscription)

    async def retrieve_subscription(
        self, provider_subscription_id: str
    ) -> Dict[str, Any]:
        """Retrieve subscription details from Stripe."""
        subscription = await self._call_stripe(
            self.stripe.Subscription.retrieve, provider_subscription_id
        )
        return self._format_subscription(subscription)

    async def retrieve_product(self, provider_product_id: str) -> Dict[str, Any]:
        """Retrieve product from Stripe and return a normalized dict."""
        product = await self._call_stripe(self.stripe.Product.retrieve, provider_product_id)
        return self._format_product(product)

    async def retrieve_price(self, provider_price_id: str) -> Dict[str, Any]:
        """Retrieve price/price_id from Stripe and return normalized dict."""
        price = await self._call_stripe(self.stripe.Price.retrieve, provider_price_id)
        return self._format_price(price)

    async def retrieve_payment(self, provider_payment_id: str) -> Dict[str, Any]:
        """Retrieve a payment intent from Stripe and return normalized dict."""
        pi = await self._call_stripe(self.stripe.PaymentIntent.retrieve, provider_payment_id)
        return self._format_payment_intent(pi)

    async def update_subscription(
        self, provider_subscription_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update subscription in Stripe."""
        current = await self._call_stripe(
            self.stripe.Subscription.retrieve, provider_subscription_id
        )
        update_params: Dict[str, Any] = {}

        if "quantity" in data:
            items = self._to_plain_dict(current).get("items", {}).get("data", [])
            if not items:
                raise ValueError("Subscription has no items to update quantity")
            update_params["items"] = [
                {"id": items[0]["id"], "quantity": data["quantity"]}
            ]

        if data.get("meta_info"):
            update_params["metadata"] = self._prepare_metadata(data["meta_info"])

        if "cancel_at_period_end" in data:
            update_params["cancel_at_period_end"] = data["cancel_at_period_end"]

        if not update_params:
            return self._format_subscription(current)

        updated = await self._call_stripe(
            self.stripe.Subscription.modify, provider_subscription_id, **update_params
        )
        return self._format_subscription(updated)

    async def cancel_subscription(
        self, provider_subscription_id: str, cancel_at_period_end: bool = True
    ) -> Dict[str, Any]:
        """Cancel a subscription in Stripe."""
        if cancel_at_period_end:
            subscription = await self._call_stripe(
                self.stripe.Subscription.modify,
                provider_subscription_id,
                cancel_at_period_end=True,
            )
        else:
            subscription = await self._call_stripe(
                self.stripe.Subscription.delete, provider_subscription_id
            )
        return self._format_subscription(subscription)

    async def process_payment(
        self,
        amount: float,
        currency: str,
        provider_customer_id: Optional[str] = None,
        payment_method_id: Optional[str] = None,
        description: Optional[str] = None,
        meta_info: Optional[Dict[str, Any]] = None,
        mandate_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Process a one-time payment with Stripe using PaymentIntents."""
        params: Dict[str, Any] = {
            "amount": self._to_stripe_amount(amount, currency),
            "currency": currency.lower(),
            "description": description,
        }
        metadata = self._prepare_metadata(meta_info)
        if metadata:
            params["metadata"] = metadata
        if provider_customer_id:
            params["customer"] = provider_customer_id
        if payment_method_id:
            params["payment_method"] = payment_method_id
            params["confirm"] = True
            params.setdefault("off_session", True)
            # If a mandate id is provided (created during a SetupIntent
            # confirm) pass it to the PaymentIntent so Stripe can complete
            # the off-session payment under the mandate.
            if mandate_id:
                params["mandate"] = mandate_id
        else:
            params["automatic_payment_methods"] = {"enabled": True}
            params["confirm"] = False

        payment_intent = await self._call_stripe(
            self.stripe.PaymentIntent.create, **params
        )
        return self._format_payment_intent(payment_intent)

    async def refund_payment(
        self, provider_payment_id: str, amount: Optional[float] = None
    ) -> Dict[str, Any]:
        """Refund a payment in Stripe."""
        refund_params: Dict[str, Any] = {"payment_intent": provider_payment_id}
        refund_currency: Optional[str] = None

        if amount is not None:
            payment_intent = await self._call_stripe(
                self.stripe.PaymentIntent.retrieve, provider_payment_id
            )
            refund_currency = self._to_plain_dict(payment_intent).get("currency", "usd")
            refund_params["amount"] = self._to_stripe_amount(amount, refund_currency)

        refund = await self._call_stripe(self.stripe.Refund.create, **refund_params)
        return self._format_refund(refund, refund_currency)

    async def webhook_handler(
        self, payload: Dict[str, Any], signature: Optional[str] = None
    ) -> Dict[str, Any]:
        """Handle webhook events from Stripe."""
        body: str
        if isinstance(payload, (bytes, bytearray)):
            body = payload.decode()
        elif isinstance(payload, str):
            body = payload
        else:
            body = json.dumps(payload)

        if signature:
            self._ensure_client()
            if not self.webhook_secret:
                raise ValueError("Webhook secret not configured for Stripe provider")
            event = self.stripe.Webhook.construct_event(
                payload=body, sig_header=signature, secret=self.webhook_secret
            )
            event_dict = self._to_plain_dict(event)
        else:
            event_dict = json.loads(body)

        event_type = event_dict.get("type", "unknown")
        standardized = self.EVENT_TYPE_MAP.get(event_type, "payment.updated")

        return {
            "event_type": event_type,
            "standardized_event_type": standardized,
            "data": event_dict.get("data", {}),
            "provider": "stripe",
        }

    async def record_usage(
        self,
        subscription_item_id: str,
        quantity: int,
        timestamp: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Record usage for metered billing with Stripe."""
        ts = int((timestamp or datetime.now(timezone.utc)).timestamp())
        usage_record = await self._call_stripe(
            self.stripe.UsageRecord.create,
            subscription_item=subscription_item_id,
            quantity=quantity,
            timestamp=ts,
            action=self.default_usage_action,
        )
        return self._format_usage_record(usage_record)

    async def _call_stripe(self, func, *args, **kwargs):
        """Execute Stripe SDK calls safely from async context."""
        self._ensure_client()
        try:
            if not getattr(self, "_run_stripe_calls_in_thread", True):
                result = func(*args, **kwargs)
                if inspect.isawaitable(result):
                    return await result
                return result

            return await asyncio.to_thread(func, *args, **kwargs)
        except Exception as exc:  # noqa: BLE001
            self._handle_stripe_error(exc)
            raise

    def _ensure_client(self) -> None:
        if not self.stripe:
            raise RuntimeError(
                "Stripe SDK is not available. Install the 'stripe' package and configure the provider."
            )

    def _handle_stripe_error(self, exc: Exception):
        if self.stripe_error and isinstance(exc, self.stripe_error.StripeError):
            logger.error("Stripe API error: %s", exc.user_message or str(exc))
        else:
            logger.error("Stripe call failed: %s", exc)

    @staticmethod
    def _timestamp_to_iso(timestamp_value: Optional[int]) -> Optional[str]:
        if timestamp_value is None:
            return None
        return datetime.fromtimestamp(timestamp_value, tz=timezone.utc).isoformat()

    def _to_stripe_amount(self, amount: float, currency: str) -> int:
        currency_code = currency.upper()
        quantize_exp = Decimal("1") if currency_code in self.ZERO_DECIMAL_CURRENCIES else Decimal("0.01")
        scaled = Decimal(str(amount)).quantize(quantize_exp, rounding=ROUND_HALF_UP)
        factor = Decimal("1") if currency_code in self.ZERO_DECIMAL_CURRENCIES else Decimal("100")
        return int((scaled * factor).to_integral_value(rounding=ROUND_HALF_UP))

    def _from_stripe_amount(self, amount: Optional[int], currency: str) -> Optional[float]:
        if amount is None:
            return None
        currency_code = currency.upper()
        if currency_code in self.ZERO_DECIMAL_CURRENCIES:
            return float(amount)
        return float(Decimal(amount) / Decimal("100"))

    @staticmethod
    def _prepare_metadata(meta_info: Optional[Dict[str, Any]]) -> Optional[Dict[str, str]]:
        if not meta_info:
            return None
        return {str(key): str(value) for key, value in meta_info.items()}

    def _format_customer(self, customer: Any) -> Dict[str, Any]:
        data = self._to_plain_dict(customer)
        return {
            "provider_customer_id": data.get("id"),
            "email": data.get("email"),
            "name": data.get("name"),
            "created_at": self._timestamp_to_iso(data.get("created")),
            "meta_info": dict(data.get("metadata") or {}),
        }

    def _format_payment_method(self, payment_method: Any) -> Dict[str, Any]:
        data = self._to_plain_dict(payment_method)
        card_details = data.get("card")
        if card_details:
            card_details = {
                "brand": card_details.get("brand"),
                "last4": card_details.get("last4"),
                "exp_month": card_details.get("exp_month"),
                "exp_year": card_details.get("exp_year"),
            }
        return {
            "payment_method_id": data.get("id"),
            "type": data.get("type"),
            "provider": "stripe",
            "created_at": self._timestamp_to_iso(data.get("created")),
            "card": card_details,
        }

    def _format_product(self, product: Any) -> Dict[str, Any]:
        data = self._to_plain_dict(product)
        return {
            "provider_product_id": data.get("id"),
            "name": data.get("name"),
            "description": data.get("description"),
            "active": data.get("active", True),
            "created_at": self._timestamp_to_iso(data.get("created")),
            "meta_info": dict(data.get("metadata") or {}),
        }

    def _format_price(self, price: Any) -> Dict[str, Any]:
        data = self._to_plain_dict(price)
        currency = data.get("currency", "usd")
        return {
            "provider_price_id": data.get("id"),
            "product_id": data.get("product"),
            "amount": self._from_stripe_amount(data.get("unit_amount"), currency),
            "currency": currency.upper(),
            "created_at": self._timestamp_to_iso(data.get("created")),
            "recurring": data.get("recurring"),
            "meta_info": dict(data.get("metadata") or {}),
        }

    def _format_subscription(self, subscription: Any) -> Dict[str, Any]:
        data = self._to_plain_dict(subscription)
        period_start = data.get("current_period_start")
        period_end = data.get("current_period_end")
        return {
            "provider_subscription_id": data.get("id"),
            "customer_id": data.get("customer"),
            "price_id": self._extract_price_id(data),
            "status": data.get("status"),
            "quantity": self._extract_quantity(data),
            "current_period_start": self._timestamp_to_iso(period_start),
            "current_period_end": self._timestamp_to_iso(period_end),
            "cancel_at_period_end": data.get("cancel_at_period_end", False),
            "created_at": self._timestamp_to_iso(data.get("created")),
            "meta_info": dict(data.get("metadata") or {}),
        }

    def _format_payment_intent(self, payment_intent: Any) -> Dict[str, Any]:
        data = self._to_plain_dict(payment_intent)
        currency = data.get("currency", "usd")
        return {
            "provider_payment_id": data.get("id"),
            "amount": self._from_stripe_amount(data.get("amount"), currency),
            "currency": currency.upper(),
            "status": data.get("status"),
            "description": data.get("description"),
            "payment_method_id": data.get("payment_method"),
            "created_at": self._timestamp_to_iso(data.get("created")),
            "meta_info": dict(data.get("metadata") or {}),
        }

    def _format_refund(self, refund: Any, currency: Optional[str]) -> Dict[str, Any]:
        data = self._to_plain_dict(refund)
        refund_currency = currency or data.get("currency", "usd")
        return {
            "provider_refund_id": data.get("id"),
            "payment_id": data.get("payment_intent"),
            "amount": self._from_stripe_amount(data.get("amount"), refund_currency),
            "status": data.get("status"),
            "created_at": self._timestamp_to_iso(data.get("created")),
        }

    def _format_usage_record(self, usage_record: Any) -> Dict[str, Any]:
        data = self._to_plain_dict(usage_record)
        return {
            "provider_usage_record_id": data.get("id"),
            "subscription_item_id": data.get("subscription_item"),
            "quantity": data.get("quantity"),
            "timestamp": self._timestamp_to_iso(data.get("timestamp")),
        }

    def _extract_price_id(self, subscription_data: Dict[str, Any]) -> Optional[str]:
        items = subscription_data.get("items")
        if isinstance(items, dict):
            data = items.get("data", [])
            if data:
                price = data[0].get("price")
                if isinstance(price, dict):
                    return price.get("id")
                return price
        plan = subscription_data.get("plan")
        if isinstance(plan, dict):
            return plan.get("id")
        return plan

    @staticmethod
    def _extract_quantity(subscription_data: Dict[str, Any]) -> Optional[int]:
        items = subscription_data.get("items")
        if isinstance(items, dict):
            data = items.get("data", [])
            if data:
                return data[0].get("quantity")
        return subscription_data.get("quantity")

    def _to_plain_dict(self, stripe_obj: Any) -> Dict[str, Any]:
        if stripe_obj is None:
            return {}
        if isinstance(stripe_obj, dict):
            return stripe_obj
        if self.stripe and hasattr(self.stripe, "util"):
            try:
                return self.stripe.util.convert_to_dict(stripe_obj)
            except Exception:  # noqa: BLE001
                pass
        if hasattr(stripe_obj, "to_dict"):
            try:
                return stripe_obj.to_dict()
            except Exception:  # noqa: BLE001
                pass
        try:
            return dict(stripe_obj)
        except Exception:  # noqa: BLE001
            mapped: Dict[str, Any] = {}
            for attr in dir(stripe_obj):
                if attr.startswith("_"):
                    continue
                try:
                    value = getattr(stripe_obj, attr)
                except AttributeError:
                    continue
                if callable(value):
                    continue
                mapped[attr] = value
            return mapped
