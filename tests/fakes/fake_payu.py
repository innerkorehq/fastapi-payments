import hashlib
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional


class FakePayU:
    """A small hermetic PayU-like provider for tests.

    Mimics the key behaviors used by the real PayUProvider in tests:
    - building hosted checkout redirect payloads
    - signing requests and responses (sha512)
    - verifying response hash on webhooks
    """

    DEFAULT_REQUEST_SEQUENCE = [
        "key",
        "txnid",
        "amount",
        "productinfo",
        "firstname",
        "email",
        *[f"udf{i}" for i in range(1, 11)],
    ]

    RESPONSE_SEQUENCE = [
        "status",
        "splitInfo",
        *[f"udf{i}" for i in range(1, 11)],
        "email",
        "firstname",
        "productinfo",
        "amount",
        "txnid",
        "key",
    ]

    def __init__(self, merchant_key: str = "merchant_key", merchant_salt: str = "merchant_salt"):
        self.merchant_key = merchant_key
        self.merchant_salt = merchant_salt
        self.checkout_url = "https://test.payu.in/_payment"

    def _generate_txn_id(self) -> str:
        return uuid.uuid4().hex[:25]

    def _format_amount(self, amount: float) -> str:
        return f"{amount:.2f}"

    def _sign_request(self, params: Dict[str, Any]) -> str:
        parts = []
        for field in self.DEFAULT_REQUEST_SEQUENCE:
            parts.append(str(params.get(field, "")))
        parts.append(self.merchant_salt)
        return hashlib.sha512("|".join(parts).encode("utf-8")).hexdigest()

    def _sign_response(self, payload: Dict[str, Any]) -> str:
        components = []
        additional_charges = payload.get("additional_charges")
        if additional_charges:
            components.append(str(additional_charges))

        components.append(self.merchant_salt)
        status = payload.get("status", "")
        components.append(status)

        split_info = payload.get("splitInfo")
        if split_info:
            components.append(split_info)

        # six empty pipes then rest of fields
        components.extend(["" for _ in range(6)])

        for field in self.RESPONSE_SEQUENCE[2:]:
            components.append(str(payload.get(field, "")))

        return hashlib.sha512("|".join(components).encode("utf-8")).hexdigest()

    def _verify_response_hash(self, payload: Dict[str, Any]) -> bool:
        received = payload.get("hash")
        if not received:
            raise ValueError("Missing payu hash")
        calc = self._sign_response(payload)
        return received.lower() == calc.lower()

    def _build_checkout_fields(self, amount: float, currency: str, description: Optional[str], meta_info: Optional[Dict[str, Any]]):
        meta_info = meta_info or {}
        # minimal required fields
        firstname = (meta_info.get("payu", {}) or {}).get("firstname") or meta_info.get("customer_context", {}).get("name", "Test")
        email = (meta_info.get("payu", {}) or {}).get("email") or meta_info.get("customer_context", {}).get("email", "test@example.com")

        fields = {
            "key": self.merchant_key,
            "txnid": (meta_info.get("payu", {}) or {}).get("txnid") or self._generate_txn_id(),
            "amount": self._format_amount(amount),
            "productinfo": (meta_info.get("payu", {}) or {}).get("productinfo") or description or "Payment",
            "firstname": firstname,
            "email": email,
            "phone": (meta_info.get("payu", {}) or {}).get("phone", ""),
            "surl": (meta_info.get("payu", {}) or {}).get("surl", "https://example.test/success"),
            "furl": (meta_info.get("payu", {}) or {}).get("furl", "https://example.test/failure"),
            "service_provider": "payu_paisa",
        }

        # add udf fields
        for i in range(1, 11):
            fields[f"udf{i}"] = (meta_info.get("payu", {}) or {}).get(f"udf{i}", "")

        fields["hash"] = self._sign_request(fields)
        return fields

    async def create_payment_method(self, provider_customer_id, payment_details):
        return {"payment_method_id": f"payu_hosted_{provider_customer_id}", "type": "hosted_checkout"}

    async def process_payment(self, amount: float, currency: str, provider_customer_id: Optional[str] = None, payment_method_id: Optional[str] = None, description: Optional[str] = None, meta_info: Optional[Dict[str, Any]] = None):
        fields = self._build_checkout_fields(amount, currency, description, meta_info)
        redirect_payload = {"action_url": self.checkout_url, "fields": fields, "method": "POST"}
        return {"provider_payment_id": fields["txnid"], "amount": float(fields["amount"]), "currency": currency, "status": "PENDING", "meta_info": {"redirect": redirect_payload}}

    async def webhook_handler(self, payload: Dict[str, Any], signature: Optional[str] = None) -> Dict[str, Any]:
        if not self._verify_response_hash(payload):
            raise ValueError("Invalid PayU webhook hash")

        status = payload.get("status", "").lower()
        if status == "success":
            standardized_event = "payment.succeeded"
        elif status == "failure":
            standardized_event = "payment.failed"
        else:
            standardized_event = "payment.pending"

        return {"event_type": payload.get("status"), "standardized_event_type": standardized_event, "provider": "payu", "data": payload}


# pytest fixture convenience
def payu_provider():
    return FakePayU()
