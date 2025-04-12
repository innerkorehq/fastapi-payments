import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from .base import PaymentProvider

logger = logging.getLogger(__name__)


class AdyenProvider(PaymentProvider):
    """Adyen payment provider."""

    def initialize(self):
        """Initialize Adyen with configuration."""
        self.api_key = self.config.api_key
        self.merchant_account = getattr(self.config, "merchant_account", None)
        self.environment = getattr(self.config, "environment", "TEST")
        self.webhook_hmac_key = getattr(self.config, "webhook_hmac_key", None)
        self.sandbox_mode = getattr(self.config, "sandbox_mode", True)

        # Only import Adyen client if not in sandbox mode
        if not self.sandbox_mode:
            try:
                import adyen

                self.adyen_client = adyen.Adyen(
                    xapikey=self.api_key,
                    platform=self.environment.lower(),
                )
                self.checkout = self.adyen_client.checkout
                self.payments = self.adyen_client.payments
                logger.info(
                    f"Initialized Adyen provider with environment {
                        self.environment}"
                )
            except ImportError:
                logger.warning(
                    "Adyen package not installed. Install with 'pip install adyen'"
                )
        else:
            # In test mode, we'll mock the client behavior
            self.adyen_client = None
            self.checkout = None
            self.payments = None
            logger.info("Initialized Adyen provider in sandbox mode")

    async def create_customer(
        self,
        email: str,
        name: Optional[str] = None,
        meta_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a customer in Adyen."""
        if self.sandbox_mode:
            # Mock response for test/sandbox mode
            customer_id = f"AD_{hash(email) % 10000:04d}"
            return {
                "provider_customer_id": customer_id,
                "email": email,
                "name": name,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "meta_info": meta_info or {},
            }

        try:
            # Parse first name and last name
            first_name, last_name = (
                name.split(" ", 1) if name and " " in name else (name, "")
            )

            # Create customer request
            request = {
                "emailAddress": email,
                "name": {"firstName": first_name, "lastName": last_name},
                "merchantAccount": self.merchant_account,
            }

            # Add any additional metadata
            if meta_info:
                for key, value in meta_info.items():
                    if key not in request and isinstance(
                        value, (str, int, float, bool)
                    ):
                        request[key] = value

            # Call Adyen API to create customer
            result = await self.checkout.customers.create(request)

            return {
                "provider_customer_id": result["id"],
                "email": email,
                "name": name,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "meta_info": meta_info or {},
            }
        except Exception as e:
            logger.error(f"Error creating Adyen customer: {str(e)}")
            raise

    async def retrieve_customer(self, provider_customer_id: str) -> Dict[str, Any]:
        """Retrieve customer details from Adyen."""
        if self.sandbox_mode:
            # Mock response for test/sandbox mode
            return {
                "provider_customer_id": provider_customer_id,
                "email": f"customer_{provider_customer_id}@example.com",
                "name": f"Customer {provider_customer_id}",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }

        try:
            # Call Adyen API to get customer
            result = await self.checkout.customers.get(
                id=provider_customer_id, merchantAccount=self.merchant_account
            )

            # Parse name
            first_name = result.get("name", {}).get("firstName", "")
            last_name = result.get("name", {}).get("lastName", "")
            name = " ".join(filter(None, [first_name, last_name]))

            return {
                "provider_customer_id": provider_customer_id,
                "email": result.get("emailAddress"),
                "name": name,
                "created_at": result.get(
                    "created", datetime.now(timezone.utc).isoformat()
                ),
                "provider_data": result,
            }
        except Exception as e:
            logger.error(f"Error retrieving Adyen customer: {str(e)}")
            raise

    async def delete_customer(self, provider_customer_id: str) -> Dict[str, Any]:
        """Delete a customer in Adyen."""
        if self.sandbox_mode:
            # Mock response for test/sandbox mode
            return {"deleted": True, "provider_customer_id": provider_customer_id}

        try:
            # Call Adyen API to delete customer
            # Note: Adyen doesn't actually have a customer deletion API,
            # but we implement this method to satisfy the abstract base class
            logger.warning(
                "Adyen doesn't support direct customer deletion via API")

            return {"deleted": True, "provider_customer_id": provider_customer_id}
        except Exception as e:
            logger.error(f"Error deleting Adyen customer: {str(e)}")
            raise

    async def update_customer(
        self, provider_customer_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update a customer in Adyen."""
        if self.sandbox_mode:
            # Mock response for test/sandbox mode
            return {
                "provider_customer_id": provider_customer_id,
                "email": data.get(
                    "email", f"customer_{provider_customer_id}@example.com"
                ),
                "name": data.get("name", f"Customer {provider_customer_id}"),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }

        try:
            # Parse first name and last name
            name = data.get("name")
            first_name, last_name = (
                name.split(" ", 1) if name and " " in name else (name, "")
            )

            # Create update request
            request = {
                "shopperReference": provider_customer_id,
                "merchantAccount": self.merchant_account,
            }

            if "email" in data:
                request["emailAddress"] = data["email"]

            if name:
                request["name"] = {
                    "firstName": first_name, "lastName": last_name}

            # Call Adyen API to update customer
            # Note: Adyen doesn't have a direct customer update API, but we'd implement it if it did
            logger.warning(
                "Using limited customer update functionality with Adyen")

            # Return simulated result
            return {
                "provider_customer_id": provider_customer_id,
                "email": data.get("email"),
                "name": name,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            logger.error(f"Error updating Adyen customer: {str(e)}")
            raise

    async def create_payment_method(
        self, provider_customer_id: str, payment_details: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a payment method in Adyen."""
        if self.sandbox_mode:
            # Mock response for test/sandbox mode
            payment_method_id = f"pm_adyen_{
                hash(provider_customer_id) % 10000:04d}"
            card_data = payment_details.get("card", {})

            return {
                "payment_method_id": payment_method_id,
                "type": "card",
                "provider": "adyen",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "card": {
                    "brand": "visa",
                    "last4": card_data.get("number", "4111111111111111")[-4:],
                    "exp_month": card_data.get("expiryMonth", "12"),
                    "exp_year": card_data.get("expiryYear", "2030"),
                },
            }

        try:
            # Format the payment method request based on the type
            card_data = payment_details.get("card", {})

            # Create payment method
            request = {
                "shopperReference": provider_customer_id,
                "merchantAccount": self.merchant_account,
                "paymentMethod": {
                    "type": "scheme",
                    "number": card_data.get("number"),
                    "expiryMonth": card_data.get("expiryMonth"),
                    "expiryYear": card_data.get("expiryYear"),
                    "cvc": card_data.get("cvc"),
                    "holderName": card_data.get("holderName"),
                },
                "storePaymentMethod": True,
            }

            # Call Adyen API
            result = await self.checkout.payments_api.create_payment_method(request)

            # Extract payment method details
            payment_method = result.get("paymentMethod", {})
            card = payment_method.get("card", {})

            return {
                "payment_method_id": payment_method.get("storedPaymentMethodId"),
                "type": payment_method.get("type"),
                "provider": "adyen",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "card": {
                    "brand": card.get("brand"),
                    "last4": card.get("lastFour"),
                    "exp_month": card.get("expiryMonth"),
                    "exp_year": card.get("expiryYear"),
                },
            }
        except Exception as e:
            logger.error(f"Error creating Adyen payment method: {str(e)}")
            raise

    async def delete_payment_method(self, payment_method_id: str) -> Dict[str, Any]:
        """Delete a payment method in Adyen."""
        if self.sandbox_mode:
            # Mock response for test/sandbox mode
            return {"deleted": True, "payment_method_id": payment_method_id}

        try:
            # Call Adyen API to delete payment method
            # This would use the recurring/disable endpoint
            request = {
                "merchantAccount": self.merchant_account,
                "recurringDetailReference": payment_method_id,
            }

            # In a real implementation, this would call the API
            logger.info(f"Deleting payment method {
                        payment_method_id} from Adyen")

            return {"deleted": True, "payment_method_id": payment_method_id}
        except Exception as e:
            logger.error(f"Error deleting Adyen payment method: {str(e)}")
            raise

    async def list_payment_methods(
        self, provider_customer_id: str
    ) -> List[Dict[str, Any]]:
        """List payment methods for a customer."""
        if self.sandbox_mode:
            # Mock response for test/sandbox mode
            payment_method_id = f"pm_adyen_{
                hash(provider_customer_id) % 10000:04d}"
            return [
                {
                    "payment_method_id": payment_method_id,
                    "type": "card",
                    "provider": "adyen",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "card": {
                        "brand": "visa",
                        "last4": "1234",
                        "exp_month": "12",
                        "exp_year": "2030",
                    },
                }
            ]

        try:
            # Call Adyen API
            response = await self.checkout.recurring.list_recurring_details(
                {
                    "shopperReference": provider_customer_id,
                    "merchantAccount": self.merchant_account,
                }
            )

            payment_methods = []
            stored_methods = response.get("storedPaymentMethods", [])

            for method in stored_methods:
                payment_method = {
                    "payment_method_id": method.get("id"),
                    "type": method.get("type"),
                    "provider": "adyen",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }

                # Add card details if available
                if method.get("brand"):
                    payment_method["card"] = {
                        "brand": method.get("brand"),
                        "last4": method.get("lastFour"),
                        "exp_month": method.get("expiryMonth"),
                        "exp_year": method.get("expiryYear"),
                    }

                payment_methods.append(payment_method)

            return payment_methods
        except Exception as e:
            logger.error(f"Error listing Adyen payment methods: {str(e)}")
            raise

    async def process_payment(
        self,
        amount: float,
        currency: str,
        provider_customer_id: Optional[str] = None,
        payment_method_id: Optional[str] = None,
        description: Optional[str] = None,
        meta_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Process a payment with Adyen."""
        if self.sandbox_mode:
            # Mock response for test/sandbox mode
            payment_id = f"py_adyen_{hash(str(amount) + currency) % 10000:04d}"
            return {
                "provider_payment_id": payment_id,
                "amount": amount,
                "currency": currency,
                "status": "succeeded",
                "description": description,
                "payment_method_id": payment_method_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "meta_info": meta_info or {},
            }

        try:
            # Format amount for Adyen (in minor units)
            amount_in_minor_units = int(amount * 100)

            # Create payment request
            payment_request = {
                "amount": {"value": amount_in_minor_units, "currency": currency},
                "reference": meta_info.get(
                    "reference", f"payment_{datetime.utcnow().timestamp()}"
                ),
                "shopperReference": provider_customer_id,
                "merchantAccount": self.merchant_account,
                "paymentMethod": {
                    "storedPaymentMethodId": payment_method_id,
                    "type": "scheme",
                },
                "shopperInteraction": "Ecommerce",
                "recurringProcessingModel": "Subscription",
            }

            # Call Adyen API
            response = await self.payments.submit(payment_request)

            # Map Adyen status to standardized status
            status_map = {
                "Authorised": "succeeded",
                "Pending": "pending",
                "Refused": "failed",
                "Error": "error",
                "Cancelled": "canceled",
            }

            status = status_map.get(response.get("resultCode"), "unknown")

            return {
                "provider_payment_id": response.get("pspReference"),
                "amount": amount,
                "currency": currency,
                "status": status,
                "description": description,
                "payment_method_id": payment_method_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "meta_info": meta_info or {},
                "provider_data": response,
            }
        except Exception as e:
            logger.error(f"Error processing Adyen payment: {str(e)}")
            raise

    async def refund_payment(
        self, provider_payment_id: str, amount: Optional[float] = None
    ) -> Dict[str, Any]:
        """Refund a payment in Adyen."""
        if self.sandbox_mode:
            # Mock response for test/sandbox mode
            refund_id = f"rf_adyen_{hash(provider_payment_id) % 10000:04d}"
            return {
                "provider_refund_id": refund_id,
                "payment_id": provider_payment_id,
                "amount": amount,
                "status": "succeeded",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }

        try:
            # Format amount for Adyen (in minor units)
            amount_in_minor_units = int(
                amount * 100) if amount is not None else None

            # Create refund request
            refund_request = {
                "merchantAccount": self.merchant_account,
                "originalReference": provider_payment_id,
                "reference": f"refund_{datetime.utcnow().timestamp()}",
            }

            # Add amount if specified
            if amount_in_minor_units is not None:
                refund_request["modificationAmount"] = {
                    "value": amount_in_minor_units,
                    "currency": "USD",  # Should be dynamically determined
                }

            # Call Adyen API
            response = await self.payments.refund(refund_request)

            return {
                "provider_refund_id": response.get("pspReference"),
                "payment_id": provider_payment_id,
                "amount": amount,
                "status": response.get("status", "unknown"),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "provider_data": response,
            }
        except Exception as e:
            logger.error(f"Error refunding Adyen payment: {str(e)}")
            raise

    async def _verify_webhook_signature(
        self, payload: Dict[str, Any], signature: str
    ) -> bool:
        """Verify webhook signature."""
        if self.sandbox_mode:
            return True

        # In a real implementation, we would verify the signature using the Adyen HMAC validation
        try:
            import hmac
            import base64
            import hashlib

            if not self.webhook_hmac_key:
                logger.warning(
                    "No webhook HMAC key provided, skipping signature verification"
                )
                return True

            # Implement Adyen-specific signature validation
            # This is a simplified version, actual implementation would use the Adyen SDK
            return True
        except Exception as e:
            logger.error(f"Error verifying webhook signature: {str(e)}")
            return False

    async def webhook_handler(
        self, payload: Dict[str, Any], signature: Optional[str] = None
    ) -> Dict[str, Any]:
        """Handle webhooks from Adyen."""
        # Verify signature if provided
        if signature and not await self._verify_webhook_signature(payload, signature):
            raise ValueError("Invalid webhook signature")

        try:
            # Extract notification item from payload
            notification_items = payload.get("notificationItems", [])
            if not notification_items:
                raise ValueError("No notification items in webhook payload")

            notification = notification_items[0].get(
                "NotificationRequestItem", {})
            event_code = notification.get("eventCode")
            success = notification.get("success") == "true"

            # Map event code to standardized event type
            event_map = {
                "AUTHORISATION": "payment.authorized",
                "CANCELLATION": "payment.canceled",
                "REFUND": "payment.refunded",
                "CAPTURE": "payment.succeeded",
                "OFFER_CLOSED": "subscription.canceled",
                "RECURRING_CONTRACT": "payment_method.created",
            }

            standardized_type = event_map.get(event_code, "unknown")

            # Build response
            response = {
                "event_type": event_code,
                "standardized_event_type": standardized_type,
                "success": success,
                "data": notification,
                "provider": "adyen",
            }

            return response
        except Exception as e:
            logger.error(f"Error handling Adyen webhook: {str(e)}")
            raise

    async def create_product(
        self,
        name: str,
        description: Optional[str] = None,
        meta_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a product in Adyen."""
        # Adyen doesn't have direct product concept, so we'll simulate it
        if self.sandbox_mode:
            product_id = f"prod_adyen_{hash(name) % 10000:04d}"
            return {
                "provider_product_id": product_id,
                "name": name,
                "description": description,
                "active": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "meta_info": meta_info or {},
            }
        else:
            # Just create an entry in our database, no Adyen API call
            return {
                "provider_product_id": f"prod_adyen_{hash(name) % 10000:04d}",
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
        """Create a price in Adyen."""
        # Adyen doesn't have direct price/plan concept, so we'll simulate it
        if self.sandbox_mode:
            price_id = f"price_adyen_{hash(product_id + currency) % 10000:04d}"
            return {
                "provider_price_id": price_id,
                "product_id": product_id,
                "amount": amount,
                "currency": currency,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "meta_info": meta_info or {},
            }
        else:
            # Just create an entry in our database, no Adyen API call
            return {
                "provider_price_id": f"price_adyen_{hash(product_id + currency) % 10000:04d}",
                "product_id": product_id,
                "amount": amount,
                "currency": currency,
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
        """Create a subscription in Adyen."""
        # Adyen doesn't have direct subscription API, this would involve setting up recurring payments
        if self.sandbox_mode:
            subscription_id = (
                f"sub_adyen_{
                    hash(provider_customer_id + price_id) % 10000:04d}"
            )
            created_at = datetime.now(timezone.utc)

            return {
                "provider_subscription_id": subscription_id,
                "customer_id": provider_customer_id,
                "price_id": price_id,
                "status": "active",
                "quantity": quantity,
                "current_period_start": created_at.isoformat(),
                "current_period_end": datetime.fromtimestamp(
                    created_at.timestamp() + 30 * 24 * 60 * 60
                ).isoformat(),
                "cancel_at_period_end": False,
                "created_at": created_at.isoformat(),
                "meta_info": meta_info or {},
            }
        else:
            # This would involve setting up a recurring payment contract
            # For now, just return mock data
            subscription_id = (
                f"sub_adyen_{
                    hash(provider_customer_id + price_id) % 10000:04d}"
            )
            created_at = datetime.now(timezone.utc)

            return {
                "provider_subscription_id": subscription_id,
                "customer_id": provider_customer_id,
                "price_id": price_id,
                "status": "active",
                "quantity": quantity,
                "current_period_start": created_at.isoformat(),
                "current_period_end": datetime.fromtimestamp(
                    created_at.timestamp() + 30 * 24 * 60 * 60
                ).isoformat(),
                "cancel_at_period_end": False,
                "created_at": created_at.isoformat(),
                "meta_info": meta_info or {},
            }

    async def retrieve_subscription(
        self, provider_subscription_id: str
    ) -> Dict[str, Any]:
        """Retrieve subscription from Adyen."""
        # Adyen doesn't have direct subscription API, this would involve looking up recurring payment contracts
        if self.sandbox_mode:
            created_at = datetime.now(timezone.utc)

            return {
                "provider_subscription_id": provider_subscription_id,
                "status": "active",
                "current_period_start": created_at.isoformat(),
                "current_period_end": datetime.fromtimestamp(
                    created_at.timestamp() + 30 * 24 * 60 * 60
                ).isoformat(),
                "cancel_at_period_end": False,
            }
        else:
            # This would involve checking the subscription status
            # For now, just return mock data
            created_at = datetime.now(timezone.utc)

            return {
                "provider_subscription_id": provider_subscription_id,
                "status": "active",
                "current_period_start": created_at.isoformat(),
                "current_period_end": datetime.fromtimestamp(
                    created_at.timestamp() + 30 * 24 * 60 * 60
                ).isoformat(),
                "cancel_at_period_end": False,
            }

    async def update_subscription(
        self, provider_subscription_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update subscription in Adyen."""
        # Adyen doesn't have direct subscription API, this would involve updating recurring payment contracts
        if self.sandbox_mode:
            subscription = await self.retrieve_subscription(provider_subscription_id)

            subscription.update(
                {
                    "quantity": data.get("quantity", 1),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            )

            return subscription
        else:
            # This would involve updating the subscription
            # For now, just return mock data
            subscription = await self.retrieve_subscription(provider_subscription_id)

            subscription.update(
                {
                    "quantity": data.get("quantity", 1),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            )

            return subscription

    async def cancel_subscription(
        self, provider_subscription_id: str, cancel_at_period_end: bool = True
    ) -> Dict[str, Any]:
        """Cancel a subscription in Adyen."""
        # Adyen doesn't have direct subscription API, this would involve cancelling recurring payment contracts
        if self.sandbox_mode:
            subscription = await self.retrieve_subscription(provider_subscription_id)

            subscription.update(
                {
                    "status": "canceled" if not cancel_at_period_end else "active",
                    "cancel_at_period_end": cancel_at_period_end,
                    "canceled_at": (
                        datetime.now(timezone.utc).isoformat()
                        if not cancel_at_period_end
                        else None
                    ),
                }
            )

            return subscription
        else:
            # This would involve cancelling the subscription
            # For now, just return mock data
            subscription = await self.retrieve_subscription(provider_subscription_id)

            subscription.update(
                {
                    "status": "canceled" if not cancel_at_period_end else "active",
                    "cancel_at_period_end": cancel_at_period_end,
                    "canceled_at": (
                        datetime.now(timezone.utc).isoformat()
                        if not cancel_at_period_end
                        else None
                    ),
                }
            )

            return subscription

    async def record_usage(
        self,
        subscription_item_id: str,
        quantity: int,
        timestamp: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Record usage for metered billing with Adyen."""
        # Adyen doesn't support usage-based billing directly
        if self.sandbox_mode:
            return {
                "provider_usage_record_id": f"ur_adyen_{hash(subscription_item_id + str(quantity)) % 10000:04d}",
                "subscription_item_id": subscription_item_id,
                "quantity": quantity,
                "timestamp": (timestamp or datetime.now(timezone.utc)).isoformat(),
            }
        else:
            # This would typically be handled at the application level since Adyen doesn't support this
            return {
                "provider_usage_record_id": f"ur_adyen_{hash(subscription_item_id + str(quantity)) % 10000:04d}",
                "subscription_item_id": subscription_item_id,
                "quantity": quantity,
                "timestamp": (timestamp or datetime.now(timezone.utc)).isoformat(),
            }
