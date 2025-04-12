from .base import PaymentProvider
from ..config.config_schema import ProviderConfig
from typing import Dict, Any, Optional, List
import aiohttp
import json
from datetime import datetime, timezone, timedelta
import logging

logger = logging.getLogger(__name__)


class PayPalProvider(PaymentProvider):
    """PayPal payment provider."""

    def initialize(self):
        """Initialize PayPal with configuration."""
        self.api_key = self.config.api_key
        # Use client_secret if api_secret is not available
        self.api_secret = getattr(
            self.config, "api_secret", getattr(
                self.config, "client_secret", None)
        )
        self.client_id = getattr(self.config, "client_id", self.api_key)
        self.client_secret = getattr(
            self.config, "client_secret", self.api_secret)
        self.sandbox_mode = getattr(self.config, "sandbox_mode", True)
        self.webhook_id = getattr(self.config, "webhook_id", None)
        self.webhook_secret = getattr(
            self.config, "webhook_secret", self.webhook_id
        )  # Use webhook_id as fallback for webhook_secret

        # API base URL depends on sandbox mode
        self.base_url = (
            "https://api-m.sandbox.paypal.com"
            if self.sandbox_mode
            else "https://api-m.paypal.com"
        )

        # Create HTTP client
        self.http_client = None
        self.access_token = None
        self.token_expires_at = None  # Add token_expires_at attribute

        logger.info(
            f"Initialized PayPal provider with sandbox mode: {
                self.sandbox_mode}"
        )

    async def _get_access_token(self) -> str:
        """
        Get an access token for API requests.

        Returns:
            str: Access token
        """
        # Return existing token if valid
        if (
            self.access_token
            and self.token_expires_at
            and datetime.now(timezone.utc) < self.token_expires_at
        ):
            return self.access_token

        # Request new token
        url = f"{self.base_url}/v1/oauth2/token"
        headers = {
            "Accept": "application/json",
            "Accept-Language": "en_US",
        }

        auth = aiohttp.BasicAuth(login=self.api_key, password=self.api_secret)

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                headers=headers,
                auth=auth,
                data={"grant_type": "client_credentials"},
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"PayPal token error: {error_text}")
                    raise Exception(
                        f"Failed to get PayPal access token: {response.status}"
                    )

                data = await response.json()

                self.access_token = data["access_token"]
                # Set token expiry with a small buffer
                expires_in = data["expires_in"]
                self.token_expires_at = datetime.now(timezone.utc) + timedelta(
                    seconds=expires_in - 60
                )

                return self.access_token

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Make a request to the PayPal API.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint
            data: Request data
            params: Query parameters

        Returns:
            Response data
        """
        access_token = await self._get_access_token()

        url = f"{self.base_url}{endpoint}"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        async with aiohttp.ClientSession() as session:
            method_func = getattr(session, method.lower())

            kwargs = {"headers": headers}
            if params:
                kwargs["params"] = params
            if data:
                kwargs["json"] = data

            async with method_func(url, **kwargs) as response:
                response_data = await response.json()

                if response.status >= 400:
                    logger.error(
                        f"PayPal API error: {
                            response.status} - {json.dumps(response_data)}"
                    )
                    error_message = response_data.get(
                        "message", str(response_data))
                    raise Exception(f"PayPal API error: {error_message}")

                return response_data

    async def create_customer(
        self,
        email: str,
        name: Optional[str] = None,
        meta_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a customer in PayPal.

        Note: PayPal doesn't have a direct equivalent to customers like Stripe.
        We'll create a virtual customer representation.

        Args:
            email: Customer email
            name: Customer name
            meta_info: Additional customer meta_info

        Returns:
            Customer data
        """
        # PayPal doesn't have a direct customer API
        # We'll return a virtual customer ID based on email
        import hashlib

        # Generate a deterministic customer ID from email
        customer_id = f"cust_{hashlib.md5(email.encode()).hexdigest()}"

        return {
            "provider_customer_id": customer_id,
            "email": email,
            "name": name,
            "created_at": datetime.now(timezone.utc),
            "meta_info": meta_info or {},
        }

    async def retrieve_customer(self, provider_customer_id: str) -> Dict[str, Any]:
        """
        Retrieve customer details from PayPal.

        Note: PayPal doesn't have a direct customer API.

        Args:
            provider_customer_id: PayPal customer ID

        Returns:
            Customer data
        """
        # PayPal doesn't have a direct customer API
        # We'll return a basic structure
        return {
            "provider_customer_id": provider_customer_id,
            "email": None,  # Not available from ID alone
            "name": None,  # Not available from ID alone
            "created_at": None,
            "meta_info": {},
        }

    async def update_customer(
        self, provider_customer_id: str, **kwargs
    ) -> Dict[str, Any]:
        """
        Update customer details in PayPal.

        Note: PayPal doesn't have a direct customer API.

        Args:
            provider_customer_id: PayPal customer ID
            **kwargs: Fields to update

        Returns:
            Updated customer data
        """
        # PayPal doesn't have a direct customer API
        return await self.retrieve_customer(provider_customer_id)

    async def delete_customer(self, provider_customer_id: str) -> Dict[str, Any]:
        """
        Delete a customer from PayPal.

        Note: PayPal doesn't have a direct customer API.

        Args:
            provider_customer_id: PayPal customer ID

        Returns:
            Result of the operation
        """
        # PayPal doesn't have a direct customer API
        return {"provider_customer_id": provider_customer_id, "deleted": True}

    async def create_payment_method(
        self, provider_customer_id: str, payment_details: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a payment method for a customer.

        Note: PayPal's approach to payment methods differs from Stripe's.

        Args:
            provider_customer_id: PayPal customer ID
            payment_details: Payment method details

        Returns:
            Payment method data
        """
        # For PayPal, payment methods are typically created during checkout
        # PayPal vault can be used for recurring payments

        if payment_details.get("type") == "paypal_vault":
            # If we have a vault token, we can store it
            token = payment_details.get("vault_token")
            if not token:
                raise Exception("PayPal vault token is required")

            # Return the vault token as payment method
            return {
                "payment_method_id": token,
                "type": "paypal_vault",
                "status": "active",
            }

        # For regular PayPal payments, methods are created during checkout
        return {
            "payment_method_id": f"pm_{datetime.now(timezone.utc).timestamp()}",
            "type": "paypal",
            "status": "pending_setup",
        }

    async def list_payment_methods(
        self, provider_customer_id: str
    ) -> List[Dict[str, Any]]:
        """
        List payment methods for a customer.

        Note: PayPal handles payment methods differently.

        Args:
            provider_customer_id: PayPal customer ID

        Returns:
            List of payment methods
        """
        # PayPal doesn't have a direct API for listing customer payment methods
        # This would typically be managed by the application
        return []

    async def delete_payment_method(self, payment_method_id: str) -> Dict[str, Any]:
        """
        Delete a payment method.

        Args:
            payment_method_id: Payment method ID

        Returns:
            Result of the operation
        """
        # PayPal doesn't have a direct API for deleting payment methods
        return {"payment_method_id": payment_method_id, "deleted": True}

    async def create_product(
        self,
        name: str,
        description: Optional[str] = None,
        meta_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a product in PayPal.

        Args:
            name: Product name
            description: Product description
            meta_info: Additional product meta_info

        Returns:
            Product data
        """
        data = {
            "name": name,
            "type": "SERVICE",
        }

        if description:
            data["description"] = description

        # Add custom meta_info as PayPal category
        if meta_info:
            data["category"] = "SOFTWARE"  # Default category
            if "category" in meta_info:
                data["category"] = meta_info["category"]

        result = await self._make_request("POST", "/v1/catalogs/products", data)

        return {
            "provider_product_id": result["id"],
            "name": result["name"],
            "description": result.get("description", ""),
            "active": True,
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
        """
        Create a price/plan in PayPal.

        Args:
            product_id: PayPal product ID
            amount: Price amount
            currency: Currency code
            interval: Billing interval (day, week, month, year)
            interval_count: Number of intervals between billings
            meta_info: Additional price meta_info

        Returns:
            Price data
        """
        # Format amount correctly (PayPal uses strings for amounts)
        amount_str = f"{amount:.2f}"

        if interval:
            # Create a billing plan (subscription)
            data = {
                "product_id": product_id,
                "name": meta_info.get("name", f"Plan for product {product_id}"),
                "billing_cycles": [
                    {
                        "frequency": {
                            "interval_unit": interval.upper(),
                            "interval_count": interval_count or 1,
                        },
                        "tenure_type": "REGULAR",
                        "sequence": 1,
                        "total_cycles": 0,  # Infinite cycles
                        "pricing_scheme": {
                            "fixed_price": {
                                "value": amount_str,
                                "currency_code": currency.upper(),
                            }
                        },
                    }
                ],
                "payment_preferences": {
                    "auto_bill_outstanding": True,
                    "setup_fee": {"value": "0", "currency_code": currency.upper()},
                    "setup_fee_failure_action": "CONTINUE",
                    "payment_failure_threshold": 3,
                },
            }

            result = await self._make_request("POST", "/v1/billing/plans", data)

            return {
                "provider_price_id": result["id"],
                "product_id": product_id,
                "amount": float(amount_str),
                "currency": currency,
                "recurring": {
                    "interval": interval,
                    "interval_count": interval_count or 1,
                },
                "meta_info": meta_info or {},
            }
        else:
            # For one-time payments, there's not really a "price" object in PayPal
            # We'll create a virtual price ID
            import hashlib

            price_id = f"price_{hashlib.md5(
                f'{product_id}-{amount}-{currency}'.encode()).hexdigest()}"

            return {
                "provider_price_id": price_id,
                "product_id": product_id,
                "amount": float(amount_str),
                "currency": currency,
                "recurring": None,
                "meta_info": meta_info or {},
            }

    async def create_subscription(
        self,
        provider_customer_id: str,
        price_id: str,
        quantity: int = 1,
        meta_info: Optional[Dict[str, Any]] = None,
        trial_period_days: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Create a subscription for a customer.

        Args:
            provider_customer_id: PayPal customer ID
            price_id: PayPal plan ID
            quantity: Number of units
            meta_info: Additional subscription meta_info
            trial_period_days: Optional trial period

        Returns:
            Subscription data
        """
        # PayPal subscriptions are normally created through the checkout process
        # This is a simplified implementation

        data = {
            "plan_id": price_id,
            "subscriber": {
                "name": {"given_name": "Customer", "surname": provider_customer_id},
                "email_address": (
                    meta_info.get("email", "customer@example.com")
                    if meta_info
                    else "customer@example.com"
                ),
            },
            "application_context": {
                "brand_name": (
                    meta_info.get("brand_name", "Your Company")
                    if meta_info
                    else "Your Company"
                ),
                "shipping_preference": "NO_SHIPPING",
                "user_action": "SUBSCRIBE_NOW",
                "payment_method": {
                    "payer_selected": "PAYPAL",
                    "payee_preferred": "IMMEDIATE_PAYMENT_REQUIRED",
                },
            },
        }

        # Add trial period if specified
        if trial_period_days:
            start_time = (
                datetime.now(timezone.utc) + timedelta(days=trial_period_days)
            ).strftime("%Y-%m-%dT%H:%M:%SZ")
            data["start_time"] = start_time

        result = await self._make_request("POST", "/v1/billing/subscriptions", data)

        return {
            "provider_subscription_id": result["id"],
            "customer_id": provider_customer_id,
            "status": result["status"],
            "current_period_start": datetime.now(timezone.utc).isoformat(),
            "current_period_end": None,  # PayPal doesn't return period end directly
            "cancel_at_period_end": False,
            "items": [{"price_id": price_id, "quantity": quantity}],
            "meta_info": meta_info or {},
        }

    async def retrieve_subscription(
        self, provider_subscription_id: str
    ) -> Dict[str, Any]:
        """
        Retrieve subscription details from PayPal.

        Args:
            provider_subscription_id: PayPal subscription ID

        Returns:
            Subscription data
        """
        result = await self._make_request(
            "GET", f"/v1/billing/subscriptions/{provider_subscription_id}"
        )

        return {
            "provider_subscription_id": result["id"],
            "customer_id": None,  # Not directly available
            "status": result["status"],
            "current_period_start": result.get("start_time"),
            "current_period_end": result.get("billing_info", {}).get(
                "next_billing_time"
            ),
            "cancel_at_period_end": result.get("billing_info", {}).get(
                "final_payment_time"
            )
            is not None,
            "items": [{"price_id": result.get("plan_id"), "quantity": 1}],
            "meta_info": {},
        }

    async def update_subscription(
        self, provider_subscription_id: str, **kwargs
    ) -> Dict[str, Any]:
        """
        Update a subscription.

        Args:
            provider_subscription_id: PayPal subscription ID
            **kwargs: Fields to update

        Returns:
            Updated subscription data
        """
        # PayPal has limited subscription update capabilities
        # Implementation depends on what needs to be updated

        if "price_id" in kwargs:
            # Update the plan
            data = [{"op": "replace", "path": "/plan_id",
                     "value": kwargs["price_id"]}]

            await self._make_request(
                "PATCH", f"/v1/billing/subscriptions/{
                    provider_subscription_id}", data
            )

        # Return updated subscription
        return await self.retrieve_subscription(provider_subscription_id)

    async def cancel_subscription(
        self, provider_subscription_id: str, cancel_at_period_end: bool = True
    ) -> Dict[str, Any]:
        """
        Cancel a subscription.

        Args:
            provider_subscription_id: PayPal subscription ID
            cancel_at_period_end: Whether to cancel at the end of the current period

        Returns:
            Updated subscription data
        """
        # PayPal doesn't support cancel_at_period_end directly
        # We'll cancel immediately

        data = {"reason": "Customer requested cancellation"}

        await self._make_request(
            "POST", f"/v1/billing/subscriptions/{
                provider_subscription_id}/cancel", data
        )

        # Return updated subscription
        return await self.retrieve_subscription(provider_subscription_id)

    async def create_invoice(
        self, provider_customer_id: str, **kwargs
    ) -> Dict[str, Any]:
        """
        Create an invoice for a customer.

        Args:
            provider_customer_id: PayPal customer ID
            **kwargs: Invoice details

        Returns:
            Invoice data
        """
        # PayPal invoices are very complex and require a lot of detail
        # This is a simplified version

        data = {
            "detail": {
                "invoice_number": kwargs.get(
                    "invoice_number",
                    f"INV-{datetime.now(timezone.utc).timestamp():.0f}",
                ),
                "currency_code": kwargs.get("currency", "USD"),
                "note": kwargs.get("description", "Invoice for services"),
                "terms_and_conditions": kwargs.get("terms", ""),
            },
            "invoicer": {
                "name": {"business_name": kwargs.get("business_name", "Your Business")}
            },
            "primary_recipients": [
                {
                    "billing_info": {
                        "email_address": kwargs.get(
                            "customer_email", "customer@example.com"
                        )
                    }
                }
            ],
            "items": [],
        }

        # Add invoice items
        for item in kwargs.get("items", []):
            data["items"].append(
                {
                    "name": item.get("description", "Service"),
                    "quantity": str(item.get("quantity", 1)),
                    "unit_amount": {
                        "currency_code": kwargs.get("currency", "USD"),
                        "value": f"{item.get('amount', 0):.2f}",
                    },
                }
            )

        result = await self._make_request("POST", "/v2/invoicing/invoices", data)

        # Send the invoice if requested
        if kwargs.get("send", False):
            await self._make_request(
                "POST", f"/v2/invoicing/invoices/{result['id']}/send"
            )

        return {
            "provider_invoice_id": result["id"],
            "customer_id": provider_customer_id,
            "status": result["status"],
            "currency": kwargs.get("currency", "USD"),
            "total_amount": sum(
                item.get("amount", 0) * item.get("quantity", 1)
                for item in kwargs.get("items", [])
            ),
            "due_date": None,  # Not directly available
            "created_at": datetime.now(timezone.utc).isoformat(),
            "meta_info": kwargs.get("meta_info", {}),
        }

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
            currency: Currency code
            provider_customer_id: PayPal customer ID
            payment_method_id: Payment method ID
            description: Payment description
            meta_info: Additional payment meta_info

        Returns:
            Payment data
        """
        # PayPal one-time payments typically involve a checkout flow
        # This is a simplified version for server-to-server payments

        # Format amount correctly
        amount_str = f"{amount:.2f}"

        data = {
            "intent": "CAPTURE",
            "purchase_units": [
                {
                    "amount": {"currency_code": currency.upper(), "value": amount_str},
                    "description": description or "One-time payment",
                }
            ],
        }

        # If we have a vault token, we can use it for direct payment
        if payment_method_id and payment_method_id.startswith("vault_"):
            data["payment_source"] = {
                "token": {"id": payment_method_id, "type": "PAYMENT_METHOD_TOKEN"}
            }

        # Create the payment
        result = await self._make_request("POST", "/v2/checkout/orders", data)

        # For direct payments with a token, capture immediately
        if payment_method_id and payment_method_id.startswith("vault_"):
            capture_result = await self._make_request(
                "POST", f"/v2/checkout/orders/{result['id']}/capture"
            )
            status = "COMPLETED"
        else:
            # Without a token, we get an approval URL that the customer needs to visit
            status = "PENDING"

        return {
            "provider_payment_id": result["id"],
            "amount": float(amount_str),
            "currency": currency,
            "status": status,
            "payment_method": payment_method_id,
            "error_message": None,
            "meta_info": meta_info or {},
        }

    async def refund_payment(
        self, provider_payment_id: str, amount: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Refund a payment, partially or fully.

        Args:
            provider_payment_id: PayPal payment ID
            amount: Optional refund amount (full refund if not specified)

        Returns:
            Refund data
        """
        # For PayPal, we need the capture ID from the payment
        # Get the payment details first
        payment = await self._make_request(
            "GET", f"/v2/checkout/orders/{provider_payment_id}"
        )

        # Find the capture ID
        capture_id = None
        for purchase_unit in payment.get("purchase_units", []):
            for capture in purchase_unit.get("payments", {}).get("captures", []):
                capture_id = capture["id"]
                break
            if capture_id:
                break

        if not capture_id:
            raise Exception("No capture found for this payment")

        # Prepare refund data
        data = {}
        if amount:
            # Partial refund
            data["amount"] = {
                "currency_code": payment["purchase_units"][0]["amount"][
                    "currency_code"
                ],
                "value": f"{amount:.2f}",
            }

        # Process the refund
        result = await self._make_request(
            "POST", f"/v2/payments/captures/{capture_id}/refund", data
        )

        return {
            "provider_refund_id": result["id"],
            "payment_id": provider_payment_id,
            "amount": float(result["amount"]["value"]) if "amount" in result else None,
            "status": result["status"],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    async def record_usage(
        self,
        provider_subscription_id: str,
        quantity: float,
        timestamp: Optional[str] = None,
        action: str = "increment",
    ) -> Dict[str, Any]:
        """
        Record usage for a usage-based subscription.

        Note: PayPal doesn't have a direct usage-based billing API like Stripe.
        This is a stub implementation.

        Args:
            provider_subscription_id: PayPal subscription ID
            quantity: Usage quantity
            timestamp: Usage timestamp
            action: Usage action (increment or set)

        Returns:
            Usage record data
        """
        # PayPal doesn't support usage-based billing directly
        # This would need to be managed by the application

        # Generate a usage record ID
        import uuid

        usage_id = f"usage_{uuid.uuid4()}"

        # Return a virtual usage record
        return {
            "id": usage_id,
            "subscription_id": provider_subscription_id,
            "quantity": quantity,
            "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
            "action": action,
        }

    async def webhook_handler(
        self, payload: Any, signature: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Handle webhooks from PayPal.

        Args:
            payload: Webhook payload
            signature: Webhook signature header

        Returns:
            Processed webhook data
        """
        # Verify webhook signature if provided
        if signature and self.webhook_secret:
            # PayPal uses a different approach for webhook verification
            # Need to make a verification request to PayPal
            webhook_id = (
                self.webhook_secret
            )  # In PayPal, webhook_secret is the webhook ID

            verification_data = {
                "auth_algo": signature.get("auth_algo"),
                "cert_url": signature.get("cert_url"),
                "transmission_id": signature.get("transmission_id"),
                "transmission_sig": signature.get("transmission_sig"),
                "transmission_time": signature.get("transmission_time"),
                "webhook_id": webhook_id,
                "webhook_event": payload,
            }

            try:
                verification = await self._make_request(
                    "POST",
                    "/v1/notifications/verify-webhook-signature",
                    verification_data,
                )

                if verification.get("verification_status") != "SUCCESS":
                    raise Exception("Invalid webhook signature")
            except Exception as e:
                logger.error(
                    f"PayPal webhook signature verification failed: {str(e)}")
                raise

        # Process different event types
        event_type = payload.get("event_type")
        resource = payload.get("resource", {})

        result = {"event_type": event_type,
                  "data": resource, "processed": True}

        # Map PayPal event types to standardized event types
        if "PAYMENT.CAPTURE.COMPLETED" in event_type:
            result["standardized_event_type"] = "payment.succeeded"
        elif "PAYMENT.CAPTURE.DENIED" in event_type:
            result["standardized_event_type"] = "payment.failed"
        elif "PAYMENT.CAPTURE.REFUNDED" in event_type:
            result["standardized_event_type"] = "payment.refunded"
        elif "BILLING.SUBSCRIPTION.CREATED" in event_type:
            result["standardized_event_type"] = "subscription.created"
        elif "BILLING.SUBSCRIPTION.UPDATED" in event_type:
            result["standardized_event_type"] = "subscription.updated"
        elif "BILLING.SUBSCRIPTION.CANCELLED" in event_type:
            result["standardized_event_type"] = "subscription.canceled"
        elif "BILLING.SUBSCRIPTION.PAYMENT.FAILED" in event_type:
            result["standardized_event_type"] = "invoice.payment_failed"
        else:
            result["standardized_event_type"] = "event.other"

        return result
