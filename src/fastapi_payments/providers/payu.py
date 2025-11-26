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
            "service_provider": self.service_provider,
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
        raise NotImplementedError("PayU hosted checkout does not support products API")

    async def create_price(
        self,
        product_id: str,
        amount: float,
        currency: str,
        interval: Optional[str] = None,
        interval_count: Optional[int] = None,
        meta_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        raise NotImplementedError("PayU hosted checkout does not support recurring prices")

    async def create_subscription(
        self,
        provider_customer_id: str,
        price_id: str,
        quantity: int = 1,
        trial_period_days: Optional[int] = None,
        meta_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        raise NotImplementedError("PayU hosted checkout does not support subscriptions")

    async def retrieve_subscription(self, provider_subscription_id: str) -> Dict[str, Any]:
        raise NotImplementedError("PayU hosted checkout does not support subscriptions")

    async def update_subscription(
        self, provider_subscription_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        raise NotImplementedError("PayU hosted checkout does not support subscriptions")

    async def cancel_subscription(
        self, provider_subscription_id: str, cancel_at_period_end: bool = True
    ) -> Dict[str, Any]:
        raise NotImplementedError("PayU hosted checkout does not support subscriptions")

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

    async def webhook_handler(
        self, payload: Dict[str, Any], signature: Optional[str] = None
    ) -> Dict[str, Any]:
        # PayU sends key-value pairs; ensure hash validation
        if not self._verify_response_hash(payload):
            raise ValueError("Invalid PayU webhook hash")

        status = payload.get("status", "").lower()
        if status == "success":
            standardized_event = "payment.succeeded"
        elif status == "failure":
            standardized_event = "payment.failed"
        else:
            standardized_event = "payment.pending"

        return {
            "event_type": payload.get("status"),
            "standardized_event_type": standardized_event,
            "provider": "payu",
            "data": payload,
        }
