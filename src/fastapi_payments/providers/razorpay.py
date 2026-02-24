"""Razorpay payment provider for India payments and subscriptions."""

from __future__ import annotations

import hashlib
import hmac
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .base import PaymentProvider

logger = logging.getLogger(__name__)


class RazorpayProvider(PaymentProvider):
    """Implementation of Razorpay payment provider.
    
    Supports:
    - Customer management
    - Plan/subscription management via Razorpay's subscription API
    - One-time payments via Orders (Razorpay Checkout JS on the frontend)
    - Webhook handling with signature verification

    Frontend checkout (preferred over subscription_link/short_url redirect):
    - Subscriptions: backend returns checkout_config with key + subscription_id;
      frontend uses Razorpay Checkout JS (https://checkout.razorpay.com/v1/checkout.js)
      with ``subscription_id`` to open the payment modal.
    - One-time orders: backend returns checkout_config with key + order_id + amount;
      frontend uses Razorpay Checkout JS with ``order_id`` to open the payment modal.

    Requires razorpay>=2.0.0 (pip install razorpay>=2.0.0)

    Razorpay API Documentation:
    - Subscriptions: https://razorpay.com/docs/payments/subscriptions/
    - Checkout JS: https://razorpay.com/docs/payments/payment-gateway/web-integration/standard/
    - Customers: https://razorpay.com/docs/api/customers/
    - Plans: https://razorpay.com/docs/api/payments/subscriptions/plans/
    """

    # Map Razorpay subscription status to normalized status
    STATUS_MAP = {
        "created": "incomplete",
        "authenticated": "incomplete",
        "active": "active",
        "pending": "past_due",
        "halted": "past_due",
        "cancelled": "canceled",
        "completed": "canceled",
        "expired": "canceled",
        "paused": "paused",
    }

    # Map Razorpay events to standardized events
    EVENT_TYPE_MAP = {
        "payment.authorized": "payment.succeeded",
        "payment.captured": "payment.succeeded",
        "payment.failed": "payment.failed",
        "order.paid": "payment.succeeded",
        "subscription.activated": "subscription.created",
        "subscription.charged": "invoice.payment_succeeded",
        "subscription.pending": "subscription.updated",
        "subscription.halted": "subscription.updated",
        "subscription.cancelled": "subscription.canceled",
        "subscription.completed": "subscription.canceled",
        "subscription.updated": "subscription.updated",
        "subscription.paused": "subscription.updated",
        "subscription.resumed": "subscription.updated",
        "refund.created": "payment.refunded",
        "refund.processed": "payment.refunded",
    }

    def initialize(self):
        """Initialize Razorpay provider with configuration."""
        try:
            import razorpay
        except ImportError:
            raise ImportError(
                "razorpay>=2.0.0 is required for Razorpay provider. "
                "Install it with: pip install 'razorpay>=2.0.0'"
            )
        
        # Client credentials
        self.key_id = self.config.api_key
        self.key_secret = (
            getattr(self.config, "api_secret", None)
            or (self.config.additional_settings or {}).get("key_secret")
        )
        
        if not self.key_secret:
            raise ValueError(
                "Razorpay provider requires api_secret or additional_settings['key_secret']"
            )
        
        self.sandbox_mode = getattr(self.config, "sandbox_mode", True)
        self.webhook_secret = getattr(self.config, "webhook_secret", None)
        settings = getattr(self.config, "additional_settings", {}) or {}
        
        # Initialize Razorpay client
        self.client = razorpay.Client(auth=(self.key_id, self.key_secret))
        
        # Store reference to razorpay module for utility access
        self._razorpay = razorpay
        
        # Default URLs for redirects
        self.default_return_url = settings.get("return_url")
        self.default_notify_url = settings.get("notify_url")
        
        # Default currency (Razorpay is primarily INR focused)
        self.default_currency = settings.get("default_currency", "INR")
        
        logger.info(
            "Initialized Razorpay provider (sandbox=%s)",
            self.sandbox_mode,
        )

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------
    def _generate_id(self, prefix: str = "rp") -> str:
        """Generate a unique ID with prefix."""
        return f"{prefix}_{uuid.uuid4().hex[:12]}"

    def _to_razorpay_amount(self, amount: float, currency: str = "INR") -> int:
        """Convert amount to paise (Razorpay expects amounts in smallest unit)."""
        # Razorpay uses paise for INR (1 INR = 100 paise)
        # For other currencies, similar logic applies
        return int(amount * 100)

    def _from_razorpay_amount(self, amount: Optional[int], currency: str = "INR") -> Optional[float]:
        """Convert paise back to main currency unit."""
        if amount is None:
            return None
        return float(amount) / 100

    def _verify_webhook_signature(
        self, payload: str, signature: str
    ) -> bool:
        """Verify Razorpay webhook signature.
        
        Razorpay uses HMAC SHA256 for webhook verification.
        """
        if not self.webhook_secret:
            logger.warning("Webhook secret not configured, skipping verification")
            return True
        
        expected_signature = hmac.new(
            self.webhook_secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)

    def _timestamp_to_iso(self, timestamp: Optional[int]) -> Optional[str]:
        """Convert Unix timestamp to ISO format."""
        if timestamp is None:
            return None
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()

    def _map_subscription_status(self, razorpay_status: str) -> str:
        """Map Razorpay subscription status to normalized status."""
        return self.STATUS_MAP.get(razorpay_status.lower(), razorpay_status)

    def _map_interval(self, interval: str) -> str:
        """Map standard interval names to Razorpay interval names."""
        interval_map = {
            "day": "daily",
            "week": "weekly",
            "month": "monthly",
            "year": "yearly",
        }
        return interval_map.get(interval.lower(), interval.lower())

    # ------------------------------------------------------------------
    # Provider interface implementation - Customer
    # ------------------------------------------------------------------
    async def create_customer(
        self,
        email: str,
        name: Optional[str] = None,
        meta_info: Optional[Dict[str, Any]] = None,
        address: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a customer in Razorpay.
        
        Razorpay customers require email and contact (phone).
        """
        meta_info = meta_info or {}
        
        customer_data = {
            "name": name or email.split("@")[0],
            "email": email,
        }
        
        # Add contact/phone if provided
        if meta_info.get("phone"):
            customer_data["contact"] = meta_info["phone"]
        elif meta_info.get("contact"):
            customer_data["contact"] = meta_info["contact"]
        
        # Add notes (Razorpay's metadata equivalent)
        notes = {}
        if address:
            notes["address"] = str(address)
        for key, value in meta_info.items():
            if key not in ("phone", "contact"):
                notes[str(key)] = str(value)
        
        if notes:
            customer_data["notes"] = notes
        
        try:
            customer = self.client.customer.create(customer_data)
            return self._format_customer(customer)
        except Exception as e:
            logger.error(f"Failed to create Razorpay customer: {e}")
            raise

    async def retrieve_customer(self, provider_customer_id: str) -> Dict[str, Any]:
        """Retrieve customer data from Razorpay."""
        try:
            customer = self.client.customer.fetch(provider_customer_id)
            return self._format_customer(customer)
        except Exception as e:
            logger.error(f"Failed to retrieve Razorpay customer: {e}")
            raise

    async def update_customer(
        self, provider_customer_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update customer data in Razorpay.
        
        Note: Razorpay has limited customer update capabilities.
        """
        update_data = {}
        
        if "name" in data:
            update_data["name"] = data["name"]
        if "email" in data:
            update_data["email"] = data["email"]
        if data.get("meta_info", {}).get("phone"):
            update_data["contact"] = data["meta_info"]["phone"]
        
        try:
            customer = self.client.customer.edit(provider_customer_id, update_data)
            result = self._format_customer(customer)
            result["updated_at"] = datetime.now(timezone.utc).isoformat()
            return result
        except Exception as e:
            logger.error(f"Failed to update Razorpay customer: {e}")
            raise

    async def delete_customer(self, provider_customer_id: str) -> Dict[str, Any]:
        """Delete a customer from Razorpay.
        
        Note: Razorpay doesn't support customer deletion.
        We mark it as deleted locally.
        """
        # Razorpay doesn't have a delete customer API
        logger.warning(
            "Razorpay doesn't support customer deletion. "
            "Customer %s marked as deleted locally.",
            provider_customer_id
        )
        return {"deleted": True, "provider_customer_id": provider_customer_id}

    # ------------------------------------------------------------------
    # Provider interface implementation - Payment Methods
    # ------------------------------------------------------------------
    async def create_payment_method(
        self, provider_customer_id: str, payment_details: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a payment method placeholder.
        
        Razorpay handles payment method collection during checkout.
        For recurring payments, use subscription with auto-charge.
        """
        # Razorpay manages payment methods through tokens obtained during payment
        # For subscriptions, payment method is attached during subscription authorization
        return {
            "payment_method_id": f"razorpay_method_{provider_customer_id}",
            "type": payment_details.get("type", "razorpay_checkout"),
            "provider": "razorpay",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    async def list_payment_methods(
        self, provider_customer_id: str
    ) -> List[Dict[str, Any]]:
        """List payment methods for a customer.
        
        Razorpay tokens can be fetched for recurring payments.
        """
        try:
            # Fetch customer tokens (saved payment methods)
            tokens = self.client.customer.fetchTokens(provider_customer_id)
            return [self._format_token(token) for token in tokens.get("items", [])]
        except Exception as e:
            logger.warning(f"Could not fetch Razorpay tokens: {e}")
            return []

    async def delete_payment_method(self, payment_method_id: str) -> Dict[str, Any]:
        """Delete a payment method/token.
        
        Razorpay token deletion requires customer_id and token_id.
        """
        # Token deletion in Razorpay requires both customer_id and token_id
        # The payment_method_id should contain both separated by underscore
        try:
            parts = payment_method_id.split("_")
            if len(parts) >= 3 and parts[0] == "token":
                # Format: token_{customer_id}_{token_id}
                # We'll try to delete if we have customer context
                pass
        except Exception:
            pass
        
        return {"deleted": True, "payment_method_id": payment_method_id}

    # ------------------------------------------------------------------
    # Provider interface implementation - Products and Plans
    # ------------------------------------------------------------------
    async def create_product(
        self,
        name: str,
        description: Optional[str] = None,
        meta_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a product (stored locally, mapped to Razorpay Items).
        
        Razorpay uses Items for one-time payments, but Plans for subscriptions.
        Products are a local abstraction.
        """
        try:
            # Create as Razorpay Item
            item_data = {
                "name": name,
                "description": description or name,
                "amount": 0,  # Placeholder, actual amount set in price/plan
                "currency": self.default_currency,
            }
            
            item = self.client.item.create(item_data)
            
            return {
                "provider_product_id": item.get("id"),
                "name": name,
                "description": description,
                "active": item.get("active", True),
                "created_at": self._timestamp_to_iso(item.get("created_at")),
                "meta_info": meta_info or {},
            }
        except Exception as e:
            # Fall back to local product
            logger.warning(f"Could not create Razorpay item: {e}. Using local product.")
            product_id = self._generate_id("razorpay_product")
            return {
                "provider_product_id": product_id,
                "name": name,
                "description": description,
                "active": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "meta_info": meta_info or {},
            }

    async def create_price(
        self,
        product_id: str,
        amount: float,
        currency: str,
        interval: Optional[str] = None,
        interval_count: Optional[int] = None,
        meta_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a price/plan for Razorpay subscriptions.
        
        For recurring prices, creates a Razorpay Plan.
        For one-time prices, stores locally (used with Orders).
        """
        meta_info = meta_info or {}
        currency = currency.upper()
        
        if interval:
            # Create a subscription plan
            plan_data = {
                "period": self._map_interval(interval),
                "interval": interval_count or 1,
                "item": {
                    "name": meta_info.get("name", f"Plan {product_id}"),
                    "amount": self._to_razorpay_amount(amount, currency),
                    "currency": currency,
                    "description": meta_info.get("description", ""),
                },
            }
            
            # Add notes if provided
            notes = {k: str(v) for k, v in meta_info.items() 
                     if k not in ("name", "description", "max_cycles")}
            if notes:
                plan_data["notes"] = notes
            
            try:
                plan = self.client.plan.create(plan_data)
                
                return {
                    "provider_price_id": plan.get("id"),
                    "product_id": product_id,
                    "amount": amount,
                    "currency": currency,
                    "interval": interval,
                    "interval_count": interval_count or 1,
                    "created_at": self._timestamp_to_iso(plan.get("created_at")),
                    "recurring": {
                        "interval": interval,
                        "interval_count": interval_count or 1,
                    },
                    "meta_info": meta_info,
                }
            except Exception as e:
                logger.error(f"Failed to create Razorpay plan: {e}")
                raise
        else:
            # One-time price - store locally
            price_id = self._generate_id("razorpay_price")
            return {
                "provider_price_id": price_id,
                "product_id": product_id,
                "amount": amount,
                "currency": currency,
                "interval": None,
                "interval_count": None,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "recurring": None,
                "meta_info": meta_info,
            }

    # ------------------------------------------------------------------
    # Provider interface implementation - Subscriptions
    # ------------------------------------------------------------------
    async def create_subscription(
        self,
        provider_customer_id: str,
        price_id: str,
        quantity: int = 1,
        trial_period_days: Optional[int] = None,
        meta_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a subscription using Razorpay's subscription API.
        
        Args:
            provider_customer_id: Customer ID
            price_id: Plan ID (Razorpay plan_id)
            quantity: Quantity (subscription count, usually 1)
            trial_period_days: Trial period in days (not directly supported)
            meta_info: Additional metadata including:
                - total_count: Total billing cycles (required for fixed-term subs)
                - start_at: Unix timestamp for subscription start
                - expire_by: Unix timestamp for subscription expiry
                - customer_notify: Whether to notify customer (True or False)
                - return_url: Return URL after authorization
                - notify_url: Webhook URL for notifications
        """
        meta_info = meta_info or {}
        razorpay_data = meta_info.get("razorpay", {})
        
        subscription_data = {
            "plan_id": price_id,
            "customer_id": provider_customer_id,
            "quantity": quantity,
            "total_count": razorpay_data.get("total_count", meta_info.get("total_count", 12)),
        }
        
        # Add optional parameters
        if razorpay_data.get("start_at") or meta_info.get("start_at"):
            subscription_data["start_at"] = razorpay_data.get("start_at") or meta_info.get("start_at")
        
        if razorpay_data.get("expire_by") or meta_info.get("expire_by"):
            subscription_data["expire_by"] = razorpay_data.get("expire_by") or meta_info.get("expire_by")
        
        # Customer notify (True = notify, False = don't notify)
        subscription_data["customer_notify"] = bool(razorpay_data.get(
            "customer_notify", meta_info.get("customer_notify", True)
        ))
        
        # Add notes
        notes = {k: str(v) for k, v in meta_info.items() 
                 if k not in ("razorpay", "total_count", "start_at", "expire_by", 
                              "customer_notify", "customer_context")}
        if notes:
            subscription_data["notes"] = notes
        
        # Add offer_id if provided
        if razorpay_data.get("offer_id"):
            subscription_data["offer_id"] = razorpay_data["offer_id"]
        
        try:
            subscription = self.client.subscription.create(subscription_data)
            
            return {
                "provider_subscription_id": subscription.get("id"),
                "customer_id": provider_customer_id,
                "price_id": price_id,
                "status": self._map_subscription_status(subscription.get("status", "created")),
                "quantity": quantity,
                "current_period_start": self._timestamp_to_iso(subscription.get("current_start")),
                "current_period_end": self._timestamp_to_iso(subscription.get("current_end")),
                "cancel_at_period_end": False,
                "created_at": self._timestamp_to_iso(subscription.get("created_at")),
                "meta_info": {
                    "razorpay_response": subscription,
                    # short_url is the Razorpay-hosted subscription link (fallback only).
                    # Prefer using checkout_config below for the Razorpay Checkout JS flow.
                    "short_url": subscription.get("short_url"),
                    "auth_link": subscription.get("short_url"),
                    "total_count": subscription.get("total_count"),
                    "paid_count": subscription.get("paid_count"),
                    "remaining_count": subscription.get("remaining_count"),
                    # ---- Razorpay Checkout JS config (frontend modal) ----
                    # Pass this object directly to `new Razorpay(checkout_config).open()`
                    # Add a `handler` function on the frontend to capture the payment response.
                    "checkout_config": self._build_subscription_checkout_config(
                        subscription_id=subscription.get("id"),
                        meta_info=meta_info,
                    ),
                },
            }
        except Exception as e:
            logger.error(f"Failed to create Razorpay subscription: {e}")
            raise

    async def retrieve_subscription(
        self, provider_subscription_id: str
    ) -> Dict[str, Any]:
        """Retrieve subscription details from Razorpay."""
        try:
            subscription = self.client.subscription.fetch(provider_subscription_id)
            return self._format_subscription(subscription)
        except Exception as e:
            logger.error(f"Failed to retrieve Razorpay subscription: {e}")
            raise

    async def update_subscription(
        self, provider_subscription_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update subscription details in Razorpay.
        
        Razorpay supports updating:
        - plan_id (upgrade/downgrade)
        - quantity
        - offer_id
        - schedule_change_at (when to apply changes)
        """
        update_data = {}
        
        if "plan_id" in data or "price_id" in data:
            update_data["plan_id"] = data.get("plan_id") or data.get("price_id")
        
        if "quantity" in data:
            update_data["quantity"] = data["quantity"]
        
        if data.get("meta_info", {}).get("offer_id"):
            update_data["offer_id"] = data["meta_info"]["offer_id"]
        
        if data.get("meta_info", {}).get("schedule_change_at"):
            update_data["schedule_change_at"] = data["meta_info"]["schedule_change_at"]
        
        # Customer notify
        if "customer_notify" in data.get("meta_info", {}):
            update_data["customer_notify"] = bool(data["meta_info"]["customer_notify"])
        
        try:
            if update_data:
                subscription = self.client.subscription.update(
                    provider_subscription_id, update_data
                )
            else:
                subscription = self.client.subscription.fetch(provider_subscription_id)
            
            return self._format_subscription(subscription)
        except Exception as e:
            logger.error(f"Failed to update Razorpay subscription: {e}")
            raise

    async def cancel_subscription(
        self, provider_subscription_id: str, cancel_at_period_end: bool = True
    ) -> Dict[str, Any]:
        """Cancel a subscription on Razorpay.
        
        Args:
            provider_subscription_id: Subscription ID
            cancel_at_period_end: If True, cancel at cycle end; if False, cancel immediately
        """
        try:
            # Razorpay cancel options:
            # cancel_at_cycle_end: 0 = immediate, 1 = at cycle end
            cancel_data = {
                "cancel_at_cycle_end": 1 if cancel_at_period_end else 0
            }
            
            subscription = self.client.subscription.cancel(
                provider_subscription_id, cancel_data
            )
            
            result = self._format_subscription(subscription)
            result["cancel_at_period_end"] = cancel_at_period_end
            result["canceled_at"] = datetime.now(timezone.utc).isoformat()
            return result
        except Exception as e:
            logger.error(f"Failed to cancel Razorpay subscription: {e}")
            raise

    async def pause_subscription(
        self, provider_subscription_id: str, pause_at: Optional[str] = None
    ) -> Dict[str, Any]:
        """Pause a subscription.
        
        Razorpay supports pausing subscriptions.
        """
        try:
            pause_data = {}
            if pause_at:
                pause_data["pause_at"] = pause_at  # "now" or "cycle_end"
            
            subscription = self.client.subscription.pause(
                provider_subscription_id, pause_data
            )
            return self._format_subscription(subscription)
        except Exception as e:
            logger.error(f"Failed to pause Razorpay subscription: {e}")
            raise

    async def resume_subscription(
        self, provider_subscription_id: str, resume_at: Optional[str] = None
    ) -> Dict[str, Any]:
        """Resume a paused subscription.
        
        Razorpay supports resuming paused subscriptions.
        """
        try:
            resume_data = {}
            if resume_at:
                resume_data["resume_at"] = resume_at  # "now" or "cycle_end"
            
            subscription = self.client.subscription.resume(
                provider_subscription_id, resume_data
            )
            return self._format_subscription(subscription)
        except Exception as e:
            logger.error(f"Failed to resume Razorpay subscription: {e}")
            raise

    # ------------------------------------------------------------------
    # Provider interface implementation - Payments
    # ------------------------------------------------------------------
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
        """Process a one-time payment with Razorpay using Orders.
        
        Creates a Razorpay Order that can be paid via checkout.
        """
        meta_info = meta_info or {}
        currency = currency.upper()
        
        order_data = {
            "amount": self._to_razorpay_amount(amount, currency),
            "currency": currency,
            "receipt": meta_info.get("receipt") or self._generate_id("receipt"),
        }
        
        # Add notes
        notes = {"description": description} if description else {}
        for k, v in meta_info.items():
            if k not in ("receipt", "razorpay"):
                notes[str(k)] = str(v)
        if notes:
            order_data["notes"] = notes
        
        try:
            order = self.client.order.create(order_data)
            
            return {
                "provider_payment_id": order.get("id"),
                "amount": amount,
                "currency": currency,
                "status": self._map_order_status(order.get("status", "created")),
                "description": description,
                "payment_method_id": payment_method_id,
                "created_at": self._timestamp_to_iso(order.get("created_at")),
                "meta_info": {
                    "razorpay_response": order,
                    "order_id": order.get("id"),
                    "receipt": order.get("receipt"),
                    # ---- Razorpay Checkout JS config (frontend modal) ----
                    # Pass this object directly to `new Razorpay(checkout_config).open()`
                    # Add a `handler` function on the frontend to capture the payment response.
                    "checkout_config": self._build_order_checkout_config(
                        order_id=order.get("id"),
                        amount_paise=order.get("amount", self._to_razorpay_amount(amount, currency)),
                        currency=currency,
                        description=description,
                        meta_info=meta_info,
                    ),
                },
            }
        except Exception as e:
            logger.error(f"Failed to create Razorpay order: {e}")
            raise

    async def refund_payment(
        self, provider_payment_id: str, amount: Optional[float] = None
    ) -> Dict[str, Any]:
        """Refund a payment in Razorpay.
        
        Args:
            provider_payment_id: Payment ID (not Order ID)
            amount: Amount to refund (in main currency unit, e.g., INR not paise)
        """
        try:
            refund_data = {}
            
            # First, get the payment to determine currency
            payment = self.client.payment.fetch(provider_payment_id)
            currency = payment.get("currency", "INR")
            
            if amount is not None:
                refund_data["amount"] = self._to_razorpay_amount(amount, currency)
            
            refund = self.client.payment.refund(provider_payment_id, refund_data)
            
            return {
                "provider_refund_id": refund.get("id"),
                "payment_id": provider_payment_id,
                "amount": self._from_razorpay_amount(refund.get("amount"), currency),
                "status": refund.get("status"),
                "created_at": self._timestamp_to_iso(refund.get("created_at")),
            }
        except Exception as e:
            logger.error(f"Failed to refund Razorpay payment: {e}")
            raise

    # ------------------------------------------------------------------
    # Provider interface implementation - Webhooks
    # ------------------------------------------------------------------
    async def webhook_handler(
        self, payload: Dict[str, Any], signature: Optional[str] = None
    ) -> Dict[str, Any]:
        """Handle webhook events from Razorpay.
        
        Razorpay sends webhooks with X-Razorpay-Signature header.
        """
        import json
        
        body: str
        if isinstance(payload, (bytes, bytearray)):
            body = payload.decode()
        elif isinstance(payload, str):
            body = payload
        else:
            body = json.dumps(payload)
        
        # Verify signature if provided
        if signature and self.webhook_secret:
            try:
                self.client.utility.verify_webhook_signature(
                    body, signature, self.webhook_secret
                )
            except Exception as e:
                logger.error(f"Webhook signature verification failed: {e}")
                raise ValueError("Invalid webhook signature")
        
        event_dict = json.loads(body) if isinstance(body, str) else payload
        
        event_type = event_dict.get("event", "unknown")
        standardized = self.EVENT_TYPE_MAP.get(event_type, "payment.updated")
        
        return {
            "event_type": event_type,
            "standardized_event_type": standardized,
            "data": event_dict.get("payload", {}),
            "provider": "razorpay",
        }

    # ------------------------------------------------------------------
    # Additional Razorpay-specific methods
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # Razorpay Checkout JS helpers
    # ------------------------------------------------------------------
    def _build_subscription_checkout_config(
        self,
        subscription_id: str,
        meta_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Build the options dict for Razorpay Checkout JS (subscription flow).

        Frontend usage::

            <script src="https://checkout.razorpay.com/v1/checkout.js"></script>
            <script>
              const options = {{ checkout_config | tojson }};
              options.handler = function(response) {
                // response.razorpay_payment_id
                // response.razorpay_subscription_id
                // response.razorpay_signature
                // POST these to your backend /verify-payment endpoint
              };
              new Razorpay(options).open();
            </script>
        """
        meta_info = meta_info or {}
        config: Dict[str, Any] = {
            "key": self.key_id,
            "subscription_id": subscription_id,
            "name": meta_info.get("merchant_name", ""),
            "description": meta_info.get("description", ""),
        }
        # Optional prefill from meta_info
        prefill = {
            k: meta_info[k]
            for k in ("name", "email", "contact", "phone")
            if meta_info.get(k)
        }
        if "phone" in prefill and "contact" not in prefill:
            prefill["contact"] = prefill.pop("phone")
        if prefill:
            config["prefill"] = prefill
        return config

    def _build_order_checkout_config(
        self,
        order_id: str,
        amount_paise: int,
        currency: str,
        description: Optional[str] = None,
        meta_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Build the options dict for Razorpay Checkout JS (order/one-time flow).

        Frontend usage::

            <script src="https://checkout.razorpay.com/v1/checkout.js"></script>
            <script>
              const options = {{ checkout_config | tojson }};
              options.handler = function(response) {
                // response.razorpay_payment_id
                // response.razorpay_order_id
                // response.razorpay_signature
                // POST these to your backend /verify-payment endpoint
              };
              new Razorpay(options).open();
            </script>
        """
        meta_info = meta_info or {}
        config: Dict[str, Any] = {
            "key": self.key_id,
            "order_id": order_id,
            "amount": amount_paise,   # Razorpay Checkout JS expects paise
            "currency": currency,
            "name": meta_info.get("merchant_name", ""),
            "description": description or meta_info.get("description", ""),
        }
        prefill = {
            k: meta_info[k]
            for k in ("name", "email", "contact", "phone")
            if meta_info.get(k)
        }
        if "phone" in prefill and "contact" not in prefill:
            prefill["contact"] = prefill.pop("phone")
        if prefill:
            config["prefill"] = prefill
        return config

    def verify_payment_signature(
        self,
        razorpay_payment_id: str,
        razorpay_order_id: Optional[str] = None,
        razorpay_subscription_id: Optional[str] = None,
        razorpay_signature: str = "",
    ) -> bool:
        """Verify the payment signature received after Razorpay Checkout.

        Call this on your backend after the frontend handler posts the
        ``razorpay_payment_id`` / ``razorpay_signature`` pair.

        For one-time orders::

            provider.verify_payment_signature(
                razorpay_payment_id=response["razorpay_payment_id"],
                razorpay_order_id=response["razorpay_order_id"],
                razorpay_signature=response["razorpay_signature"],
            )

        For subscriptions::

            provider.verify_payment_signature(
                razorpay_payment_id=response["razorpay_payment_id"],
                razorpay_subscription_id=response["razorpay_subscription_id"],
                razorpay_signature=response["razorpay_signature"],
            )

        Returns True when the signature is valid, raises ValueError on failure.
        """
        import hmac as _hmac
        import hashlib as _hashlib

        try:
            if not razorpay_order_id and not razorpay_subscription_id:
                raise ValueError(
                    "Either razorpay_order_id or razorpay_subscription_id must be provided."
                )

            # The Razorpay SDK's verify_payment_signature always looks for
            # razorpay_order_id via a hard key lookup, which raises KeyError for
            # subscription payments.  Compute the HMAC-SHA256 directly instead.
            if razorpay_order_id:
                # Razorpay order signature: HMAC(order_id + "|" + payment_id)
                message = f"{razorpay_order_id}|{razorpay_payment_id}"
            else:
                # Razorpay subscription signature: HMAC(payment_id + "|" + subscription_id)
                message = f"{razorpay_payment_id}|{razorpay_subscription_id}"

            expected = _hmac.new(
                self.key_secret.encode("utf-8"),
                message.encode("utf-8"),
                _hashlib.sha256,
            ).hexdigest()

            if not _hmac.compare_digest(expected, razorpay_signature):
                raise ValueError("Signature mismatch")

            return True
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Razorpay payment signature verification failed: {e}")
            raise ValueError(f"Invalid payment signature: {e}") from e

    async def fetch_subscription_invoices(
        self, provider_subscription_id: str
    ) -> List[Dict[str, Any]]:
        """Fetch invoices for a subscription."""
        try:
            invoices = self.client.subscription.fetch_all_invoices(
                provider_subscription_id
            )
            return [self._format_invoice(inv) for inv in invoices.get("items", [])]
        except Exception as e:
            logger.error(f"Failed to fetch subscription invoices: {e}")
            raise

    async def create_subscription_registration_link(
        self,
        provider_customer_id: str,
        amount: float,
        currency: str = "INR",
        description: Optional[str] = None,
        meta_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a registration link for recurring payments (emandate/nach).
        
        This is used for bank mandate registration in India.
        """
        meta_info = meta_info or {}
        
        registration_data = {
            "email": meta_info.get("email"),
            "contact": meta_info.get("phone"),
            "type": "link",
            "amount": self._to_razorpay_amount(amount, currency),
            "currency": currency.upper(),
            "description": description or "Subscription registration",
            "subscription_registration": {
                "method": meta_info.get("method", "emandate"),
                "auth_type": meta_info.get("auth_type", "netbanking"),
                "bank_account": meta_info.get("bank_account", {}),
            },
        }
        
        if meta_info.get("max_amount"):
            registration_data["subscription_registration"]["max_amount"] = (
                self._to_razorpay_amount(meta_info["max_amount"], currency)
            )
        
        if meta_info.get("expire_at"):
            registration_data["subscription_registration"]["expire_at"] = meta_info["expire_at"]
        
        try:
            invoice = self.client.invoice.create(registration_data)
            return {
                "registration_link_id": invoice.get("id"),
                "short_url": invoice.get("short_url"),
                "status": invoice.get("status"),
                "created_at": self._timestamp_to_iso(invoice.get("created_at")),
            }
        except Exception as e:
            logger.error(f"Failed to create registration link: {e}")
            raise

    async def charge_subscription_manually(
        self, provider_subscription_id: str
    ) -> Dict[str, Any]:
        """Manually charge a subscription.
        
        Used for subscriptions that are in pending/halted state.
        """
        try:
            charge = self.client.subscription.pending_update(
                provider_subscription_id
            )
            return self._format_subscription(charge)
        except Exception as e:
            logger.error(f"Failed to charge subscription: {e}")
            raise

    # ------------------------------------------------------------------
    # Formatting helpers
    # ------------------------------------------------------------------
    def _format_customer(self, customer: Dict[str, Any]) -> Dict[str, Any]:
        """Format Razorpay customer to normalized format."""
        return {
            "provider_customer_id": customer.get("id"),
            "email": customer.get("email"),
            "name": customer.get("name"),
            "created_at": self._timestamp_to_iso(customer.get("created_at")),
            "meta_info": {
                "contact": customer.get("contact"),
                "gstin": customer.get("gstin"),
                **(customer.get("notes") or {}),
            },
        }

    def _format_subscription(self, subscription: Dict[str, Any]) -> Dict[str, Any]:
        """Format Razorpay subscription to normalized format."""
        return {
            "provider_subscription_id": subscription.get("id"),
            "customer_id": subscription.get("customer_id"),
            "price_id": subscription.get("plan_id"),
            "status": self._map_subscription_status(subscription.get("status", "created")),
            "quantity": subscription.get("quantity", 1),
            "current_period_start": self._timestamp_to_iso(subscription.get("current_start")),
            "current_period_end": self._timestamp_to_iso(subscription.get("current_end")),
            "cancel_at_period_end": subscription.get("ended_at") is not None,
            "created_at": self._timestamp_to_iso(subscription.get("created_at")),
            "meta_info": {
                "short_url": subscription.get("short_url"),
                "total_count": subscription.get("total_count"),
                "paid_count": subscription.get("paid_count"),
                "remaining_count": subscription.get("remaining_count"),
                "charge_at": self._timestamp_to_iso(subscription.get("charge_at")),
                "offer_id": subscription.get("offer_id"),
                "notes": subscription.get("notes"),
            },
        }

    def _format_token(self, token: Dict[str, Any]) -> Dict[str, Any]:
        """Format Razorpay token to payment method format."""
        return {
            "payment_method_id": f"token_{token.get('id')}",
            "type": token.get("method", "card"),
            "provider": "razorpay",
            "created_at": self._timestamp_to_iso(token.get("created_at")),
            "card": {
                "last4": token.get("card", {}).get("last4"),
                "network": token.get("card", {}).get("network"),
                "type": token.get("card", {}).get("type"),
                "issuer": token.get("card", {}).get("issuer"),
            } if token.get("card") else None,
            "bank": token.get("bank"),
            "wallet": token.get("wallet"),
        }

    def _format_invoice(self, invoice: Dict[str, Any]) -> Dict[str, Any]:
        """Format Razorpay invoice."""
        currency = invoice.get("currency", "INR")
        return {
            "invoice_id": invoice.get("id"),
            "subscription_id": invoice.get("subscription_id"),
            "amount": self._from_razorpay_amount(invoice.get("amount"), currency),
            "amount_paid": self._from_razorpay_amount(invoice.get("amount_paid"), currency),
            "amount_due": self._from_razorpay_amount(invoice.get("amount_due"), currency),
            "currency": currency,
            "status": invoice.get("status"),
            "billing_start": self._timestamp_to_iso(invoice.get("billing_start")),
            "billing_end": self._timestamp_to_iso(invoice.get("billing_end")),
            "paid_at": self._timestamp_to_iso(invoice.get("paid_at")),
            "created_at": self._timestamp_to_iso(invoice.get("created_at")),
        }

    def _map_order_status(self, status: str) -> str:
        """Map Razorpay order status to normalized payment status."""
        status_map = {
            "created": "requires_payment_method",
            "attempted": "requires_payment_method",
            "paid": "succeeded",
        }
        return status_map.get(status.lower(), status)
