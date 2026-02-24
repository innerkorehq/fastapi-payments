"""PayU hosted checkout payment provider."""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .base import PaymentProvider

logger = logging.getLogger(__name__)


class PayUProvider(PaymentProvider):
    """Implementation of PayU hosted checkout provider."""

    # PayU hash sequence per documentation:
    # sha512(key|txnid|amount|productinfo|firstname|email|udf1|udf2|udf3|udf4|udf5||||||si_details|SALT)
    # We model the reserved pipes explicitly as udf6..udf10 then include si_details.
    DEFAULT_REQUEST_SEQUENCE: List[str] = [
        "key",
        "txnid",
        "amount",
        "productinfo",
        "firstname",
        "email",
        "udf1",
        "udf2",
        "udf3",
        "udf4",
        "udf5",
        "udf6",
        "udf7",
        "udf8",
        "udf9",
        "udf10",
        "si_details",
    ]

    # Order derived from PayU documentation (reverse hashing)
    RESPONSE_SEQUENCE: List[str] = [
        "status",
        "splitInfo",
        "udf5",
        "udf4",
        "udf3",
        "udf2",
        "udf1",
        "email",
        "firstname",
        "productinfo",
        "amount",
        "txnid",
        "key",
    ]

    def initialize(self):
        """Initialize PayU provider with configuration."""

        self.merchant_key = self.config.api_key
        self.merchant_salt = (
            getattr(self.config, "api_secret", None)
            or getattr(self.config, "merchant_salt", None)
            or self.config.additional_settings.get("salt")
        )

        if not self.merchant_salt:
            raise ValueError(
                "PayU provider requires api_secret or additional_settings['salt']"
            )

        self.sandbox_mode = getattr(self.config, "sandbox_mode", True)
        settings = getattr(self.config, "additional_settings", {}) or {}

        self.checkout_url = settings.get(
            "hosted_checkout_url",
            "https://test.payu.in/_payment"
            if self.sandbox_mode
            else "https://secure.payu.in/_payment",
        )
        self.verify_payment_url = settings.get(
            "verify_payment_url",
            "https://test.payu.in/merchant/postservice.php?form=2"
            if self.sandbox_mode
            else "https://info.payu.in/merchant/postservice.php?form=2",
        )
        self.default_success_url = settings.get("success_url")
        self.default_failure_url = settings.get("failure_url")
        self.default_cancel_url = settings.get("cancel_url")
        self.service_provider = settings.get("service_provider", "payu_paisa")
        self.request_sequence = settings.get(
            "request_hash_sequence", self.DEFAULT_REQUEST_SEQUENCE
        )
        
        # Recurring payment API endpoints
        base_url = "https://test.payu.in" if self.sandbox_mode else "https://info.payu.in"
        self.si_transaction_url = settings.get(
            "si_transaction_url",
            f"{base_url}/merchant/postservice?form=2",
        )
        self.mandate_revoke_url = settings.get(
            "mandate_revoke_url",
            f"{base_url}/merchant/postservice?form=2",
        )
        self.pre_debit_notify_url = settings.get(
            "pre_debit_notify_url",
            f"{base_url}/merchant/postservice?form=2",
        )

        logger.info("Initialized PayU provider (sandbox=%s)", self.sandbox_mode)

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------
    def _generate_txn_id(self) -> str:
        return uuid.uuid4().hex[:25]

    @staticmethod
    def _format_amount(amount: float) -> str:
        return f"{amount:.2f}"

    def _sign_request(self, params: Dict[str, Any]) -> str:
        parts: List[str] = []
        for field in self.request_sequence:
            parts.append(str(params.get(field, "")))
        parts.append(self.merchant_salt)
        hash_string = "|".join(parts)
        
        # Log hash string for debugging (masking salt)
        if self.merchant_salt:
            masked_hash_string = hash_string.replace(self.merchant_salt, "***")
        else:
            masked_hash_string = hash_string
        logger.info(f"PayU Request Hash String: {masked_hash_string}")
        
        return hashlib.sha512(hash_string.encode("utf-8")).hexdigest()

    def _sign_response(self, payload: Dict[str, Any]) -> str:
        components: List[str] = []
        additional_charges = payload.get("additional_charges")
        if additional_charges:
            components.append(str(additional_charges))

        components.append(self.merchant_salt)
        status = payload.get("status", "")
        components.append(status)

        split_info = payload.get("splitInfo")
        if split_info:
            components.append(split_info)

        # PayU expects six empty pipes between status block and udf fields
        components.extend(["" for _ in range(6)])

        for field in self.RESPONSE_SEQUENCE[2:]:  # skip status & splitInfo handled
            components.append(str(payload.get(field, "")))

        return hashlib.sha512("|".join(components).encode("utf-8")).hexdigest()

    def _verify_response_hash(self, payload: Dict[str, Any]) -> bool:
        received_hash = payload.get("hash")
        if not received_hash:
            raise ValueError("PayU webhook payload missing hash field")
        calculated = self._sign_response(payload)
        return received_hash.lower() == calculated.lower()
    
    def _sign_si_request(self, command: str, var1: str, var2: Optional[str] = None) -> str:
        """Sign PayU SI API requests (si_transaction, mandate_revoke, pre_debit_SI)."""
        if var2:
            hash_string = f"{self.merchant_key}|{command}|{var1}|{var2}|{self.merchant_salt}"
        else:
            hash_string = f"{self.merchant_key}|{command}|{var1}|{self.merchant_salt}"
        return hashlib.sha512(hash_string.encode("utf-8")).hexdigest()
    
    async def _make_si_api_request(self, command: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Make a request to PayU SI APIs (si_transaction, mandate_revoke, pre_debit_SI)."""
        import httpx
        
        payload = {
            "key": self.merchant_key,
            "command": command,
            **params,
        }
        
        # Add hash based on command type
        var1 = params.get("var1", "")
        var2 = params.get("var2")
        payload["hash"] = self._sign_si_request(command, var1, var2)
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.si_transaction_url,
                data=payload,
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    def _build_checkout_fields(
        self,
        amount: float,
        currency: str,
        description: Optional[str],
        meta_info: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        meta_info = meta_info or {}
        payu_data = meta_info.get("payu", {})
        customer_context = meta_info.get("customer_context", {})

        firstname = payu_data.get("firstname") or customer_context.get("name")
        email = payu_data.get("email") or customer_context.get("email")

        if not firstname:
            raise ValueError("PayU checkout requires the customer's first name")
        if not email:
            raise ValueError("PayU checkout requires the customer's email address")

        product_info = payu_data.get("productinfo") or description or "Payment"
        phone = payu_data.get("phone") or customer_context.get("phone", "")
        surl = payu_data.get("surl") or self.default_success_url
        furl = payu_data.get("furl") or self.default_failure_url

        if not surl or not furl:
            raise ValueError(
                "PayU checkout requires success (surl) and failure (furl) callback URLs"
            )

        fields: Dict[str, Any] = {
            "key": self.merchant_key,
            "txnid": payu_data.get("txnid") or self._generate_txn_id(),
            "amount": self._format_amount(amount),
            "productinfo": product_info,
            "firstname": firstname,
            "email": email,
            "phone": phone,
            "surl": surl,
            "furl": furl,
        }

        cancel_url = payu_data.get("curl") or self.default_cancel_url
        if cancel_url:
            fields["curl"] = cancel_url

        for i in range(1, 11):
            key = f"udf{i}"
            fields[key] = payu_data.get(key, "")

        optional_fields = ["user_token", "offer_key", "offer_auto_apply", "cart_details", "extra_charges"]
        for field in optional_fields:
            if field in payu_data:
                fields[field] = payu_data[field]

        if payu_data.get("additional_params"):
            fields.update(payu_data["additional_params"])

        fields["hash"] = self._sign_request(fields)
        return fields

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
        customer_id = f"payu_{uuid.uuid4().hex[:12]}"
        return {
            "provider_customer_id": customer_id,
            "email": email,
            "name": name,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "meta_info": {**(meta_info or {}), **({"address": address} if address else {})},
        }

    async def retrieve_customer(self, provider_customer_id: str) -> Dict[str, Any]:
        return {
            "provider_customer_id": provider_customer_id,
            "email": None,
            "name": None,
            "meta_info": {},
        }

    async def update_customer(
        self, provider_customer_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        return {"provider_customer_id": provider_customer_id, **data}

    async def delete_customer(self, provider_customer_id: str) -> Dict[str, Any]:
        return {"deleted": True, "provider_customer_id": provider_customer_id}

    async def create_payment_method(
        self, provider_customer_id: str, payment_details: Dict[str, Any]
    ) -> Dict[str, Any]:
        return {
            "payment_method_id": f"payu_hosted_{provider_customer_id}",
            "type": "hosted_checkout",
            "provider": "payu",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    async def list_payment_methods(
        self, provider_customer_id: str
    ) -> List[Dict[str, Any]]:
        return [
            {
                "payment_method_id": f"payu_hosted_{provider_customer_id}",
                "type": "hosted_checkout",
                "provider": "payu",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        ]

    async def delete_payment_method(self, payment_method_id: str) -> Dict[str, Any]:
        return {"deleted": True, "payment_method_id": payment_method_id}

    async def create_product(
        self,
        name: str,
        description: Optional[str] = None,
        meta_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a product for PayU subscriptions (stored locally, not on PayU)."""
        product_id = f"payu_product_{uuid.uuid4().hex[:12]}"
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
        """Create a price/plan for PayU subscriptions (stored locally)."""
        price_id = f"payu_price_{uuid.uuid4().hex[:12]}"
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
        """Create a subscription using PayU SI (Standing Instruction) registration.
        
        This initiates a payment consent transaction that must be completed by the customer.
        The meta_info should contain subscription details like amount, interval, etc.
        """
        meta_info = meta_info or {}
        payu_data = meta_info.get("payu", {})
        customer_context = meta_info.get("customer_context", {})
        
        # Extract subscription parameters
        amount = meta_info.get("amount") or payu_data.get("amount")
        if not amount:
            raise ValueError("Subscription amount is required in meta_info")
        
        firstname = payu_data.get("firstname") or customer_context.get("name")
        email = payu_data.get("email") or customer_context.get("email")
        
        if not firstname or not email:
            raise ValueError("Customer firstname and email are required for subscription")
        
        # SI-specific fields
        si_start_date = payu_data.get("si_start_date")  # Format: dd-MM-yyyy
        si_amount = self._format_amount(amount * quantity)
        si_period = payu_data.get("si_period", "monthly").upper()  # DAILY, WEEKLY, MONTHLY, YEARLY
        
        product_info = payu_data.get("productinfo") or meta_info.get("description", "Subscription")
        
        if not si_start_date:
            raise ValueError("si_start_date is required in meta_info['payu'] (format: dd-MM-yyyy)")
        
        # Build checkout fields with SI parameters
        fields: Dict[str, Any] = {
            "key": self.merchant_key,
            "txnid": payu_data.get("txnid") or self._generate_txn_id(),
            "amount": si_amount,
            "productinfo": product_info,
            "firstname": firstname,
            "email": email,
            "phone": payu_data.get("phone") or customer_context.get("phone", ""),
            "surl": payu_data.get("surl") or self.default_success_url,
            "furl": payu_data.get("furl") or self.default_failure_url,
            # SI-specific parameters for Pay and Subscribe (SI=4)
            "si": "4",  # Enable SI (Pay and Subscribe) - supports Cards, NetBanking, UPI
            "si_start_date": si_start_date,
            "si_amount": si_amount,
            "si_period": si_period,
            # Required for UPI recurring payments
            "api_version": "7",  # Required for UPI SI
            "freeCharge": "1",  # Enable all payment modes including UPI for SI
        }
        
        # Optional SI fields
        if "si_end_date" in payu_data:
            fields["si_end_date"] = payu_data["si_end_date"]  # Format: dd-MM-yyyy
        if "si_cycles" in payu_data:
            fields["si_cycles"] = payu_data["si_cycles"]  # Number of cycles
        if "si_remarks" in payu_data:
            fields["si_remarks"] = payu_data["si_remarks"]

        # Support si_details object (per PayU docs) and payment mode controls
        # If provided, include as JSON string under 'si_details'.
        si_details = payu_data.get("si_details")
        if si_details:
            import json
            # Normalize payment_modes to lowercase list
            pm = si_details.get("payment_modes")
            if pm and isinstance(pm, (list, tuple)):
                si_details["payment_modes"] = [str(x).lower() for x in pm]

            fields["si_details"] = json.dumps(si_details)

            # If UPI is requested, ensure UPI-specific flags are present
            if "upi" in (si_details.get("payment_modes") or []):
                fields.setdefault("api_version", "14")
                fields.setdefault("freeCharge", "1")
        
        # Add UDF fields
        for i in range(1, 11):
            key = f"udf{i}"
            fields[key] = payu_data.get(key, "")
        
        # Add cancel URL if provided
        cancel_url = payu_data.get("curl") or self.default_cancel_url
        if cancel_url:
            fields["curl"] = cancel_url
        
        # Sign the request
        fields["hash"] = self._sign_request(fields)
        
        subscription_id = f"payu_sub_{uuid.uuid4().hex[:12]}"
        
        redirect_payload = {
            "action_url": self.checkout_url,
            "fields": fields,
            "method": "POST",
        }
        
        return {
            "provider_subscription_id": subscription_id,
            "provider_customer_id": provider_customer_id,
            "price_id": price_id,
            "status": "pending",  # Waiting for customer to complete SI registration
            "quantity": quantity,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "current_period_start": None,
            "current_period_end": None,
            "meta_info": {
                "redirect": redirect_payload,
                "txnid": fields["txnid"],
                "si_period": si_period,
                "si_start_date": si_start_date,
            },
        }

    async def retrieve_subscription(self, provider_subscription_id: str) -> Dict[str, Any]:
        """Retrieve subscription status by checking mandate status.
        
        For cards: Use check_mandate_status API
        For UPI: Use upi_mandate_status API
        
        Note: You need to pass the mandate token (received after SI registration) 
        in the provider_subscription_id or store it separately.
        """
        # This is a simplified implementation. In production, you should:
        # 1. Store the mandate token after successful SI registration
        # 2. Use check_mandate_status or upi_mandate_status APIs
        # 3. Parse the response to determine subscription status
        
        logger.warning(
            "retrieve_subscription called for %s. Full mandate status checking requires "
            "storing mandate tokens and calling PayU's check_mandate_status API.",
            provider_subscription_id
        )
        
        return {
            "provider_subscription_id": provider_subscription_id,
            "status": "unknown",  # Possible: active, paused, cancelled
            "meta_info": {
                "note": "Implement check_mandate_status API call for real-time status"
            },
        }

    async def update_subscription(
        self, provider_subscription_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update subscription using PayU mandate modification APIs.
        
        For cards: Use modify recurring payment API
        For UPI: Use upi_mandate_modify command
        
        Args:
            provider_subscription_id: Mandate token or subscription ID
            data: Update data (should contain mandate_token, new amount, etc.)
        """
        mandate_token = data.get("mandate_token") or provider_subscription_id
        
        # For UPI mandate modification
        if data.get("payment_method") == "upi":
            params = {
                "var1": mandate_token,
                "var2": data.get("new_amount", ""),
            }
            
            # Optional parameters
            if "new_start_date" in data:
                params["var3"] = data["new_start_date"]
            if "new_end_date" in data:
                params["var4"] = data["new_end_date"]
            
            try:
                response = await self._make_si_api_request("upi_mandate_modify", params)
                return {
                    "provider_subscription_id": provider_subscription_id,
                    "status": "modified",
                    "meta_info": {"api_response": response},
                }
            except Exception as e:
                logger.error("Failed to modify UPI mandate: %s", str(e))
                raise
        
        # For card-based subscriptions, use modify API (implementation similar to UPI)
        logger.warning(
            "update_subscription called for card mandate. Implement specific "
            "modify_recurring_payment API call."
        )
        
        return {
            "provider_subscription_id": provider_subscription_id,
            "status": "update_pending",
            "meta_info": data,
        }

    async def cancel_subscription(
        self, provider_subscription_id: str, cancel_at_period_end: bool = True
    ) -> Dict[str, Any]:
        """Cancel subscription using PayU mandate_revoke API.
        
        For cards: Use mandate_revoke command
        For UPI: Use upi_mandate_revoke command
        For Net Banking: Use si_cancel command
        
        Args:
            provider_subscription_id: Should contain the mandate token
            cancel_at_period_end: Not applicable for PayU (cancels immediately)
        """
        # Extract mandate token (should be stored in subscription meta_info)
        mandate_token = provider_subscription_id
        
        # Default to card mandate revoke
        # In production, determine payment method from stored subscription data
        command = "mandate_revoke"
        
        params = {
            "var1": mandate_token,
        }
        
        try:
            response = await self._make_si_api_request(command, params)
            
            return {
                "provider_subscription_id": provider_subscription_id,
                "status": "canceled",
                "canceled_at": datetime.now(timezone.utc).isoformat(),
                "meta_info": {
                    "api_response": response,
                    "note": "PayU mandates are canceled immediately",
                },
            }
        except Exception as e:
            logger.error("Failed to cancel mandate %s: %s", mandate_token, str(e))
            raise

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
        # PayU hosted checkout does not use mandate IDs but we accept the
        # argument so callers (like PaymentService) can pass it without error.
        _ = mandate_id
        fields = self._build_checkout_fields(amount, currency, description, meta_info)

        redirect_payload = {
            "action_url": self.checkout_url,
            "fields": fields,
            "method": "POST",
        }

        return {
            "provider_payment_id": fields["txnid"],
            "amount": float(fields["amount"]),
            "currency": currency,
            "status": "PENDING",
            "meta_info": {"redirect": redirect_payload},
        }

    async def refund_payment(
        self, provider_payment_id: str, amount: Optional[float] = None
    ) -> Dict[str, Any]:
        raise NotImplementedError("PayU hosted checkout does not support refunds via API")

    async def si_transaction(
        self,
        mandate_token: str,
        amount: float,
        txnid: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute a recurring payment transaction using si_transaction API.
        
        This should be called after SI registration is complete and you have a mandate token.
        
        Args:
            mandate_token: The mandate token received after successful SI registration
            amount: Transaction amount
            txnid: Optional transaction ID (auto-generated if not provided)
        
        Returns:
            Transaction response from PayU
        """
        params = {
            "var1": mandate_token,
            "var2": self._format_amount(amount),
            "var3": txnid or self._generate_txn_id(),
        }
        
        try:
            response = await self._make_si_api_request("si_transaction", params)
            return {
                "provider_payment_id": params["var3"],
                "mandate_token": mandate_token,
                "amount": amount,
                "status": "processing",
                "meta_info": {"api_response": response},
            }
        except Exception as e:
            logger.error("SI transaction failed: %s", str(e))
            raise
    
    async def pre_debit_notify(
        self,
        mandate_token: str,
        amount: float,
        debit_date: str,
    ) -> Dict[str, Any]:
        """Send pre-debit notification to customer using pre_debit_SI API.
        
        As per RBI guidelines, merchants must notify customers before debiting.
        
        Args:
            mandate_token: The mandate token
            amount: Amount to be debited
            debit_date: Date of debit (format: dd-MM-yyyy)
        
        Returns:
            API response
        """
        params = {
            "var1": mandate_token,
            "var2": self._format_amount(amount),
            "var3": debit_date,
        }
        
        try:
            response = await self._make_si_api_request("pre_debit_SI", params)
            return {
                "mandate_token": mandate_token,
                "notification_sent": True,
                "amount": amount,
                "debit_date": debit_date,
                "meta_info": {"api_response": response},
            }
        except Exception as e:
            logger.error("Pre-debit notification failed: %s", str(e))
            raise

    async def webhook_handler(
        self, payload: Dict[str, Any], signature: Optional[str] = None
    ) -> Dict[str, Any]:
        # PayU sends key-value pairs; ensure hash validation
        if not self._verify_response_hash(payload):
            raise ValueError("Invalid PayU webhook hash")

        status = payload.get("status", "").lower()
        
        # Check if this is a subscription/SI event
        # SI=4 transactions will have si="4" in the response, or mandate_token/card_token
        is_si = (
            payload.get("si") in ["1", "4"] 
            or payload.get("mandate_token") is not None
            or payload.get("card_token") is not None
        )
        
        if status == "success":
            if is_si:
                # For SI=4, the initial transaction creates the subscription
                standardized_event = "subscription.created"
            else:
                standardized_event = "payment.succeeded"
        elif status == "failure":
            standardized_event = "payment.failed"
        else:
            standardized_event = "payment.pending"

        return {
            "event_type": payload.get("status"),
            "standardized_event_type": standardized_event,
            "provider": "payu",
            "is_subscription": is_si,
            "data": payload,
        }
