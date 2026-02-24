"""Cashfree payment provider for India and international payments."""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .base import PaymentProvider

logger = logging.getLogger(__name__)


class CashfreeProvider(PaymentProvider):
    """Implementation of Cashfree payment provider.
    
    Supports:
    - Collect from India (for overseas businesses accepting Indian payments)
    - Collect from World (for Indian businesses accepting international payments)
    - Subscription management via Cashfree's subscription API
    """

    def initialize(self):
        """Initialize Cashfree provider with configuration."""
        try:
            from cashfree_pg.configuration import Configuration
            from cashfree_pg.api_client import ApiClient
        except ImportError:
            raise ImportError(
                "cashfree_pg is required for Cashfree provider. "
                "Install it with: pip install cashfree_pg"
            )
        
        # Client credentials
        self.client_id = self.config.api_key
        self.client_secret = (
            getattr(self.config, "api_secret", None)
            or self.config.additional_settings.get("client_secret")
        )
        
        if not self.client_secret:
            raise ValueError(
                "Cashfree provider requires api_secret or additional_settings['client_secret']"
            )
        
        self.sandbox_mode = getattr(self.config, "sandbox_mode", True)
        settings = getattr(self.config, "additional_settings", {}) or {}
        
        # Set up SDK configuration
        self.configuration = Configuration()
        self.configuration.api_key = {
            'x-client-id': self.client_id,
            'x-client-secret': self.client_secret
        }
        self.configuration.host = "https://sandbox.cashfree.com" if self.sandbox_mode else "https://api.cashfree.com"
        
        # Create API client
        self.api_client = ApiClient(self.configuration)
        
        # Determine if this is India collection or global collection
        self.collection_mode = settings.get("collection_mode", "india")  # "india" or "global"
        
        # Default URLs for redirects
        self.default_return_url = settings.get("return_url")
        self.default_notify_url = settings.get("notify_url")
        
        logger.info(
            "Initialized Cashfree provider (sandbox=%s, mode=%s)",
            self.sandbox_mode,
            self.collection_mode,
        )

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------
    def _generate_order_id(self) -> str:
        """Generate a unique order ID."""
        return f"order_{uuid.uuid4().hex[:20]}"
    
    def _generate_subscription_id(self) -> str:
        """Generate a unique subscription ID."""
        return f"sub_{uuid.uuid4().hex[:20]}"
    
    def _verify_webhook_signature(
        self, payload: str, signature: str, timestamp: str
    ) -> bool:
        """Verify Cashfree webhook signature.
        
        Cashfree uses HMAC SHA256 for webhook verification.
        Signature format: timestamp + raw_body
        """
        import hmac
        
        signature_data = f"{timestamp}{payload}"
        expected_signature = hmac.new(
            self.client_secret.encode("utf-8"),
            signature_data.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)

    # ------------------------------------------------------------------
    # Provider interface implementation
    # ------------------------------------------------------------------
    async def create_customer(
        self,
        email: str,
        name: Optional[str] = None,
        meta_info: Optional[Dict[str, Any]] = None,
        address: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a customer (stored locally, Cashfree doesn't have customer objects)."""
        customer_id = f"cashfree_{uuid.uuid4().hex[:12]}"
        
        customer_data = {
            "provider_customer_id": customer_id,
            "email": email,
            "name": name,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "meta_info": {**(meta_info or {}), **({"address": address} if address else {})},
        }
        
        # Store phone from meta_info if provided
        if meta_info and "phone" in meta_info:
            customer_data["phone"] = meta_info["phone"]
        
        return customer_data

    async def retrieve_customer(self, provider_customer_id: str) -> Dict[str, Any]:
        """Retrieve customer data (stored locally)."""
        return {
            "provider_customer_id": provider_customer_id,
            "email": None,
            "name": None,
            "meta_info": {},
        }

    async def update_customer(
        self, provider_customer_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update customer data (stored locally)."""
        return {"provider_customer_id": provider_customer_id, **data}

    async def delete_customer(self, provider_customer_id: str) -> Dict[str, Any]:
        """Delete a customer (stored locally)."""
        return {"deleted": True, "provider_customer_id": provider_customer_id}

    async def create_payment_method(
        self, provider_customer_id: str, payment_details: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a payment method placeholder (Cashfree handles payment collection)."""
        return {
            "payment_method_id": f"cashfree_method_{provider_customer_id}",
            "type": "cashfree_checkout",
            "provider": "cashfree",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    async def list_payment_methods(
        self, provider_customer_id: str
    ) -> List[Dict[str, Any]]:
        """List payment methods for a customer."""
        return [
            {
                "payment_method_id": f"cashfree_method_{provider_customer_id}",
                "type": "cashfree_checkout",
                "provider": "cashfree",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        ]

    async def delete_payment_method(self, payment_method_id: str) -> Dict[str, Any]:
        """Delete a payment method."""
        return {"deleted": True, "payment_method_id": payment_method_id}

    async def create_product(
        self,
        name: str,
        description: Optional[str] = None,
        meta_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a product for Cashfree subscriptions (stored locally)."""
        product_id = f"cashfree_product_{uuid.uuid4().hex[:12]}"
        return {
            "provider_product_id": product_id,
            "name": name,
            "description": description,
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
        """Create a price/plan for Cashfree subscriptions.
        
        Cashfree subscription plans can be created via API.
        """
        price_id = f"cashfree_price_{uuid.uuid4().hex[:12]}"
        
        # Map interval to Cashfree's interval type
        interval_map = {
            "day": "DAILY",
            "week": "WEEKLY",
            "month": "MONTHLY",
            "year": "YEARLY",
        }
        
        cashfree_interval = interval_map.get(
            (interval or "month").lower(), "MONTHLY"
        )
        
        # Create plan on Cashfree (optional - can also be done during subscription creation)
        plan_data = {
            "plan_id": price_id,
            "plan_name": meta_info.get("name", f"Plan {price_id}") if meta_info else f"Plan {price_id}",
            "plan_type": "PERIODIC",
            "plan_currency": currency.upper(),
            "plan_amount": int(amount * 100),  # Convert to paise/cents
            "plan_interval_type": cashfree_interval,
            "plan_intervals": interval_count or 1,
            "plan_max_cycles": meta_info.get("max_cycles") if meta_info else None,
            "plan_max_amount": meta_info.get("max_amount") if meta_info else None,
        }
        
        # Remove None values
        plan_data = {k: v for k, v in plan_data.items() if v is not None}
        
        try:
            # Try to create plan on Cashfree using SDK
            from cashfree_pg.models.create_plan_request import CreatePlanRequest
            
            plan_request = CreatePlanRequest(
                plan_id=price_id,
                plan_name=meta_info.get("name", f"Plan {price_id}") if meta_info else f"Plan {price_id}",
                plan_type="PERIODIC",
                plan_currency=currency.upper(),
                plan_amount=int(amount * 100),  # Convert to paise/cents
                plan_interval_type=cashfree_interval,
                plan_intervals=interval_count or 1,
            )
            
            # Add optional fields
            if meta_info and meta_info.get("max_cycles"):
                plan_request.plan_max_cycles = meta_info["max_cycles"]
            if meta_info and meta_info.get("max_amount"):
                plan_request.plan_max_amount = meta_info["max_amount"]
            
            endpoint = "/pg/subscriptions/plans"
            response = await self.api_client.call_api(
                endpoint, 'POST',
                header_params={'Content-Type': 'application/json'},
                body=plan_request.to_dict() if hasattr(plan_request, 'to_dict') else plan_request,
                response_type=object
            )
            
            logger.info(f"Created Cashfree plan: {price_id}")
        except Exception as e:
            logger.warning(f"Could not create Cashfree plan: {e}. Will store locally.")
        
        return {
            "provider_price_id": price_id,
            "product_id": product_id,
            "amount": amount,
            "currency": currency,
            "interval": interval or "month",
            "interval_count": interval_count or 1,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "meta_info": meta_info or {},
        }

    async def create_subscription(
        self,
        provider_customer_id: str,
        price_id: str,
        quantity: int = 1,
        trial_period_days: Optional[int] = None,
        meta_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a subscription using Cashfree's subscription API.
        
        Args:
            provider_customer_id: Customer ID
            price_id: Price/Plan ID
            quantity: Quantity (default 1)
            trial_period_days: Trial period in days
            meta_info: Additional metadata including:
                - customer_name: Customer name (required)
                - customer_email: Customer email (required)
                - customer_phone: Customer phone (required)
                - return_url: Return URL after payment
                - notify_url: Webhook URL for notifications
        """
        meta_info = meta_info or {}
        cashfree_data = meta_info.get("cashfree", {})
        customer_context = meta_info.get("customer_context", {})
        
        # Extract customer details
        customer_name = (
            cashfree_data.get("customer_name")
            or customer_context.get("name")
            or meta_info.get("customer_name")
        )
        customer_email = (
            cashfree_data.get("customer_email")
            or customer_context.get("email")
            or meta_info.get("customer_email")
        )
        customer_phone = (
            cashfree_data.get("customer_phone")
            or customer_context.get("phone")
            or meta_info.get("customer_phone")
        )
        
        if not customer_name or not customer_email:
            raise ValueError(
                "Customer name and email are required for Cashfree subscriptions"
            )
        
        # Phone is required by Cashfree SDK, provide default if not specified
        if not customer_phone:
            customer_phone = "9999999999"  # Default phone number
            logger.warning("Customer phone not provided for Cashfree subscription, using default phone number")
        
        # Generate subscription ID
        subscription_id = self._generate_subscription_id()
        
        # Build subscription creation payload
        subscription_customer_details = {
            "customer_id": provider_customer_id,
            "customer_name": customer_name,
            "customer_email": customer_email,
        }
        
        if customer_phone:
            subscription_customer_details["customer_phone"] = customer_phone
        
        subscription_data = {
            "subscription_id": subscription_id,
            "plan_id": price_id,
            "subscription_customer_details": subscription_customer_details,
            "subscription_first_charge_date": cashfree_data.get("first_charge_date"),
            "subscription_expiry_date": cashfree_data.get("expiry_date"),
            "subscription_note": cashfree_data.get("note"),
            "subscription_tags": cashfree_data.get("tags"),
            "subscription_return_url": (
                cashfree_data.get("return_url") or self.default_return_url
            ),
            "subscription_notify_url": (
                cashfree_data.get("notify_url") or self.default_notify_url
            ),
        }
        
        # Remove None values
        subscription_data = {
            k: v for k, v in subscription_data.items() if v is not None
        }
        
        try:
            # Create subscription using API client
            from cashfree_pg.models.create_subscription_request import CreateSubscriptionRequest
            
            # Build subscription request
            from cashfree_pg.models.subscription_customer_details import SubscriptionCustomerDetails
            
            subscription_request = CreateSubscriptionRequest(
                subscription_id=subscription_id,
                customer_details=SubscriptionCustomerDetails(
                    customer_name=customer_name,
                    customer_email=customer_email,
                    customer_phone=customer_phone,
                ),
                plan_details={
                    "plan_id": price_id,
                },
                return_url=(
                    cashfree_data.get("return_url") or self.default_return_url
                ),
                notify_url=(
                    cashfree_data.get("notify_url") or self.default_notify_url
                ),
            )
            # Add optional fields
            if cashfree_data.get("first_charge_date"):
                subscription_request.first_charge_date = cashfree_data["first_charge_date"]
            if cashfree_data.get("expiry_date"):
                subscription_request.expiry_date = cashfree_data["expiry_date"]
            if cashfree_data.get("note"):
                subscription_request.note = cashfree_data["note"]
            if cashfree_data.get("tags"):
                subscription_request.tags = cashfree_data["tags"]
            
            # Make API call using the client
            endpoint = "/pg/subscriptions"
            response = await self.api_client.call_api(
                endpoint, 'POST',
                header_params={'Content-Type': 'application/json'},
                body=subscription_request.to_dict() if hasattr(subscription_request, 'to_dict') else subscription_request,
                response_type=object
            )
            
            subscription_data = response[0] if response else {}
            
            return {
                "provider_subscription_id": subscription_id,
                "provider_customer_id": provider_customer_id,
                "price_id": price_id,
                "status": self._map_subscription_status(subscription_data.get("status", "active")),
                "quantity": quantity,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "current_period_start": subscription_data.get("current_period_start"),
                "current_period_end": subscription_data.get("current_period_end"),
                "meta_info": {
                    "cashfree_response": subscription_data,
                    "authorization_url": subscription_data.get("authorization_url"),
                },
            }
        except Exception as e:
            logger.error(f"Failed to create Cashfree subscription: {e}")
            raise

    async def retrieve_subscription(
        self, provider_subscription_id: str
    ) -> Dict[str, Any]:
        """Retrieve subscription details from Cashfree."""
        try:
            endpoint = f"/pg/subscriptions/{provider_subscription_id}"
            response = await self.api_client.call_api(
                endpoint, 'GET',
                header_params={'Content-Type': 'application/json'},
                response_type=object
            )
            
            subscription_data = response[0] if response else {}
            
            return {
                "provider_subscription_id": provider_subscription_id,
                "status": self._map_subscription_status(subscription_data.get("status", "active")),
                "current_period_start": subscription_data.get("current_period_start"),
                "current_period_end": subscription_data.get("current_period_end"),
                "meta_info": {"cashfree_response": subscription_data},
            }
        except Exception as e:
            logger.error(f"Failed to retrieve Cashfree subscription: {e}")
            raise

    async def cancel_subscription(
        self, provider_subscription_id: str, cancel_at_period_end: bool = True
    ) -> Dict[str, Any]:
        """Cancel a subscription on Cashfree.
        
        Args:
            provider_subscription_id: Subscription ID
            cancel_at_period_end: Whether to cancel at period end (Cashfree cancels immediately)
        """
        try:
            endpoint = f"/pg/subscriptions/{provider_subscription_id}/cancel"
            response = await self.api_client.call_api(
                endpoint, 'POST',
                header_params={'Content-Type': 'application/json'},
                response_type=object
            )
            
            return {
                "provider_subscription_id": provider_subscription_id,
                "status": "canceled",
                "canceled_at": datetime.now(timezone.utc).isoformat(),
                "cancel_at_period_end": cancel_at_period_end,
                "meta_info": {"cashfree_response": response if response else None},
            }
        except Exception as e:
            logger.error(f"Failed to cancel Cashfree subscription: {e}")
            raise

    async def update_subscription(
        self, provider_subscription_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update a subscription on Cashfree.
        
        Note: Cashfree has limited subscription update capabilities.
        Most changes require canceling and creating a new subscription.
        """
        try:
            # Cashfree doesn't have a direct update API
            # For now, we'll retrieve and return current state
            # In production, you might need to cancel and recreate
            endpoint = f"/pg/subscriptions/{provider_subscription_id}"
            response = await self.api_client.call_api(
                endpoint, 'GET',
                header_params={'Content-Type': 'application/json'},
                response_type=object
            )
            
            subscription_data = response if response else {}
            
            return {
                "provider_subscription_id": provider_subscription_id,
                "status": self._map_subscription_status(subscription_data.get("status", "active")),
                "meta_info": {
                    "cashfree_response": subscription_data,
                    "note": "Cashfree subscriptions have limited update capabilities",
                },
            }
        except Exception as e:
            logger.error(f"Failed to update Cashfree subscription: {e}")
            raise

    async def process_payment(
        self,
        amount: float,
        currency: str,
        provider_customer_id: str,
        description: Optional[str] = None,
        meta_info: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Process a one-time payment using Cashfree.
        
        This creates a payment order and returns checkout details.
        """
        meta_info = meta_info or {}
        cashfree_data = meta_info.get("cashfree", {})
        customer_context = meta_info.get("customer_context", {})
        
        # Extract customer details
        customer_name = (
            cashfree_data.get("customer_name")
            or customer_context.get("name")
        )
        customer_email = (
            cashfree_data.get("customer_email")
            or customer_context.get("email")
        )
        customer_phone = (
            cashfree_data.get("customer_phone")
            or customer_context.get("phone")
        )
        
        if not customer_name or not customer_email:
            raise ValueError(
                "Customer name and email are required for Cashfree payments"
            )
        
        # Phone is required by Cashfree SDK, provide default if not specified
        if not customer_phone:
            customer_phone = "9999999999"  # Default phone number
            logger.warning("Customer phone not provided for Cashfree payment, using default phone number")
        
        try:
            # Create order using SDK
            from cashfree_pg.models.create_order_request import CreateOrderRequest
            
            # Generate order ID
            order_id = cashfree_data.get("order_id") or self._generate_order_id()
            
            # Build order request
            from cashfree_pg.models.customer_details import CustomerDetails
            
            order_request = CreateOrderRequest(
                order_id=order_id,
                order_amount=amount,
                order_currency=currency.upper(),
                customer_details=CustomerDetails(
                    customer_id=provider_customer_id,
                    customer_name=customer_name,
                    customer_email=customer_email,
                    customer_phone=customer_phone,
                ),
                order_note=description or cashfree_data.get("note"),
            )
            # Add tags if provided
            if cashfree_data.get("tags"):
                order_request.order_tags = cashfree_data["tags"]
            
            # Add return and notify URLs
            if cashfree_data.get("return_url") or self.default_return_url:
                order_meta = {
                    "return_url": cashfree_data.get("return_url") or self.default_return_url,
                }
                if cashfree_data.get("notify_url") or self.default_notify_url:
                    order_meta["notify_url"] = (
                        cashfree_data.get("notify_url") or self.default_notify_url
                    )
                order_request.order_meta = order_meta
            
            # Make API call
            endpoint = "/pg/orders"
            response = await self.api_client.call_api(
                endpoint, 'POST',
                header_params={'Content-Type': 'application/json'},
                body=order_request.to_dict() if hasattr(order_request, 'to_dict') else order_request,
                response_type=object
            )
            
            order_data = response[0] if response else {}
            
            payment_id = f"cashfree_payment_{uuid.uuid4().hex[:12]}"
            
            return {
                "provider_payment_id": payment_id,
                "amount": amount,
                "currency": currency,
                "status": "pending",
                "provider_customer_id": provider_customer_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "meta_info": {
                    "cashfree_order_id": order_id,
                    "cashfree_response": order_data,
                    "payment_session_id": order_data.get("payment_session_id"),
                    "order_token": order_data.get("order_token"),
                },
            }
        except Exception as e:
            logger.error(f"Failed to create Cashfree order: {e}")
            raise

    async def refund_payment(
        self,
        provider_payment_id: str,
        amount: Optional[float] = None,
        meta_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Refund a payment on Cashfree."""
        meta_info = meta_info or {}
        cashfree_data = meta_info.get("cashfree", {})
        
        # Get order ID from meta_info
        order_id = cashfree_data.get("order_id")
        if not order_id:
            raise ValueError("order_id is required in meta_info['cashfree'] for refunds")
        
        # Generate refund ID
        refund_id = f"refund_{uuid.uuid4().hex[:20]}"
        
        try:
            # Create refund using SDK
            from cashfree_pg.models.order_create_refund_request import OrderCreateRefundRequest
            
            refund_request = OrderCreateRefundRequest(
                refund_id=refund_id,
                refund_amount=amount,
            )
            
            # Add refund note if provided
            if cashfree_data.get("refund_note"):
                refund_request.refund_note = cashfree_data["refund_note"]
            
            endpoint = f"/pg/orders/{order_id}/refunds"
            response = await self.api_client.call_api(
                endpoint, 'POST',
                header_params={'Content-Type': 'application/json'},
                body=refund_request.to_dict() if hasattr(refund_request, 'to_dict') else refund_request,
                response_type=object
            )
            
            refund_data = response[0] if response else {}
            
            return {
                "provider_refund_id": refund_id,
                "amount": amount or refund_data.get("refund_amount"),
                "status": self._map_refund_status(refund_data.get("refund_status")),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "meta_info": {"cashfree_response": refund_data},
            }
        except Exception as e:
            logger.error(f"Failed to create Cashfree refund: {e}")
            raise

    async def webhook_handler(
        self, payload: Dict[str, Any], signature: Optional[str] = None
    ) -> Dict[str, Any]:
        """Handle Cashfree webhook events.
        
        Cashfree sends webhook events for:
        - Payment success/failure
        - Subscription events
        - Refund events
        
        Args:
            payload: Webhook payload
            signature: Optional webhook signature for verification
        """
        event_type = payload.get("type")
        
        if not event_type:
            raise ValueError("Webhook payload missing 'type' field")
        
        # Map Cashfree event types to standardized event types
        event_mapping = {
            "PAYMENT_SUCCESS_WEBHOOK": "payment.succeeded",
            "PAYMENT_FAILED_WEBHOOK": "payment.failed",
            "PAYMENT_USER_DROPPED_WEBHOOK": "payment.canceled",
            "SUBSCRIPTION_ACTIVATED": "subscription.created",
            "SUBSCRIPTION_CHARGED_SUCCESSFULLY": "subscription.payment_succeeded",
            "SUBSCRIPTION_CHARGE_FAILED": "subscription.payment_failed",
            "SUBSCRIPTION_CANCELLED": "subscription.canceled",
            "SUBSCRIPTION_PAUSED": "subscription.paused",
            "SUBSCRIPTION_RESUMED": "subscription.resumed",
            "REFUND_PROCESSED": "refund.succeeded",
            "REFUND_FAILED": "refund.failed",
        }
        
        standardized_event = event_mapping.get(event_type, "unknown")
        
        return {
            "event_id": payload.get("event_id") or f"evt_{uuid.uuid4().hex[:12]}",
            "event_type": event_type,
            "standardized_event_type": standardized_event,
            "data": payload.get("data", {}),
            "timestamp": payload.get("event_time") or datetime.now(timezone.utc).isoformat(),
            "raw_payload": payload,
        }

    # ------------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------------
    def _map_subscription_status(self, cashfree_status: Optional[str]) -> str:
        """Map Cashfree subscription status to standardized status."""
        status_map = {
            "INITIALIZED": "pending",
            "ACTIVE": "active",
            "PAUSED": "paused",
            "CANCELLED": "canceled",
            "EXPIRED": "canceled",
            "COMPLETED": "completed",
        }
        return status_map.get(cashfree_status or "", "unknown")
    
    def _map_refund_status(self, cashfree_status: Optional[str]) -> str:
        """Map Cashfree refund status to standardized status."""
        status_map = {
            "SUCCESS": "succeeded",
            "PENDING": "pending",
            "FAILED": "failed",
            "CANCELLED": "canceled",
        }
        return status_map.get(cashfree_status or "", "unknown")
