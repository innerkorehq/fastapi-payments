import json
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4


class FakeStripe:
    """Minimal in-memory Stripe replacement for unit tests.

    This mirrors the previous in-test FakeStripe and is intentionally
    simplistic — it implements the small subset of Stripe SDK behavior used
    by our unit tests (Customer, PaymentMethod, Product, Price, Subscription,
    PaymentIntent, Refund, UsageRecord, Webhook).
    """

    def __init__(self):
        self.api_key = None
        self.api_version = None
        self.util = SimpleNamespace(convert_to_dict=lambda obj: obj)
        self.error = SimpleNamespace(StripeError=Exception)
        self.Webhook = SimpleNamespace(construct_event=self._construct_event)

        self.customers = {}
        self.payment_methods = {}
        self.products = {}
        self.prices = {}
        self.subscriptions = {}
        self.payment_intents = {}
        self.refunds = {}
        self.usage_records = {}

        self.Customer = SimpleNamespace(
            create=self._customer_create,
            retrieve=self._customer_retrieve,
            modify=self._customer_modify,
            delete=self._customer_delete,
        )
        self.PaymentMethod = SimpleNamespace(
            create=self._payment_method_create,
            attach=self._payment_method_attach,
            list=self._payment_method_list,
            detach=self._payment_method_detach,
        )
        self.Product = SimpleNamespace(create=self._product_create)
        self.Price = SimpleNamespace(create=self._price_create)
        self.Subscription = SimpleNamespace(
            create=self._subscription_create,
            retrieve=self._subscription_retrieve,
            modify=self._subscription_modify,
            delete=self._subscription_delete,
        )
        self.PaymentIntent = SimpleNamespace(
            create=self._payment_intent_create,
            retrieve=self._payment_intent_retrieve,
        )
        self.Refund = SimpleNamespace(create=self._refund_create)
        self.UsageRecord = SimpleNamespace(create=self._usage_record_create)

    @staticmethod
    def _construct_event(payload: str, sig_header: str, secret: str):
        del sig_header, secret
        return json.loads(payload)

    @staticmethod
    def _now() -> int:
        return int(datetime.now(timezone.utc).timestamp())

    @staticmethod
    def _generate_id(prefix: str) -> str:
        return f"{prefix}_{uuid4().hex[:12]}"

    def _customer_create(self, **kwargs):
        customer_id = self._generate_id("cus")
        customer = {
            "id": customer_id,
            "email": kwargs.get("email"),
            "name": kwargs.get("name"),
            "created": self._now(),
            "metadata": kwargs.get("metadata") or {},
        }
        self.customers[customer_id] = customer
        return customer

    def _customer_retrieve(self, customer_id: str):
        return self.customers[customer_id]

    def _customer_modify(self, customer_id: str, **kwargs):
        customer = self.customers[customer_id]
        customer.update({k: v for k, v in kwargs.items() if v is not None})
        if "invoice_settings" in kwargs:
            customer["invoice_settings"] = kwargs["invoice_settings"]
        if "metadata" in kwargs:
            customer["metadata"] = kwargs["metadata"]
        return customer

    def _customer_delete(self, customer_id: str):
        self.customers.pop(customer_id, None)
        return {"id": customer_id, "deleted": True}

    def _payment_method_create(self, **kwargs):
        # Ensure we don't accidentally receive unknown parameters that should
        # have been filtered before calling create (eg. payment_method_id)
        if "payment_method_id" in kwargs:
            raise ValueError("Unexpected parameter 'payment_method_id' sent to PaymentMethod.create")
        if "unexpected_key" in kwargs:
            raise ValueError("Unexpected key forwarded to PaymentMethod.create")

        pm_id = self._generate_id("pm")
        card = kwargs.get("card") or {}
        # Accept server-side test 'token' like 'pm_card_visa' and map to a
        # representative card number so tests can pass PaymentMethod ids.
        token = card.get("token") or kwargs.get("token")
        if token:
            # map a few common test tokens to numbers so subsequent flows can
            # simulate behavior described in Stripe docs
            if token == "pm_card_visa" or token == "tok_visa":
                card_number = "4242424242424242"
            elif token == "pm_card_3ds_required":
                card_number = "4000000000003220"
            elif token == "pm_card_declined":
                card_number = "4000000000000002"
            else:
                card_number = None
            if card_number:
                card["number"] = card_number
        payment_method = {
            "id": pm_id,
            "type": kwargs.get("type", "card"),
            "card": {
                "brand": card.get("brand", "visa"),
                "last4": (card.get("number") or "0000")[-4:],
                "exp_month": card.get("exp_month"),
                "exp_year": card.get("exp_year"),
            },
            "created": self._now(),
            "customer": None,
            "card": card,
        }
        self.payment_methods[pm_id] = payment_method
        return payment_method

    def _payment_method_attach(self, pm_id: str, **kwargs):
        payment_method = self.payment_methods[pm_id]
        payment_method["customer"] = kwargs.get("customer")
        return payment_method

    def _payment_method_list(self, **kwargs):
        customer = kwargs.get("customer")
        pm_type = kwargs.get("type")
        data = [
            pm
            for pm in self.payment_methods.values()
            if pm.get("customer") == customer and pm.get("type") == pm_type
        ]
        return {"data": data}

    def _payment_method_detach(self, pm_id: str):
        payment_method = self.payment_methods[pm_id]
        payment_method["customer"] = None
        return payment_method

    def _product_create(self, **kwargs):
        product_id = self._generate_id("prod")
        product = {
            "id": product_id,
            "name": kwargs.get("name"),
            "description": kwargs.get("description"),
            "active": kwargs.get("active", True),
            "created": self._now(),
            "metadata": kwargs.get("metadata") or {},
        }
        self.products[product_id] = product
        return product

    def _price_create(self, **kwargs):
        price_id = self._generate_id("price")
        price = {
            "id": price_id,
            "product": kwargs["product"],
            "unit_amount": kwargs["unit_amount"],
            "currency": kwargs.get("currency", "usd"),
            "recurring": kwargs.get("recurring"),
            "metadata": kwargs.get("metadata") or {},
            "created": self._now(),
        }
        self.prices[price_id] = price
        return price

    def _subscription_create(self, **kwargs):
        subscription_id = self._generate_id("sub")
        price_id = kwargs["items"][0]["price"]
        quantity = kwargs["items"][0].get("quantity", 1)
        subscription_item_id = self._generate_id("si")
        period_start = self._now()
        period_end = period_start + 30 * 24 * 60 * 60
        subscription = {
            "id": subscription_id,
            "customer": kwargs.get("customer"),
            "items": {
                "data": [
                    {
                        "id": subscription_item_id,
                        "price": self.prices[price_id],
                        "quantity": quantity,
                    }
                ]
            },
            "status": "active",
            "current_period_start": period_start,
            "current_period_end": period_end,
            "cancel_at_period_end": False,
            "created": period_start,
            "metadata": kwargs.get("metadata") or {},
        }
        self.subscriptions[subscription_id] = subscription
        return subscription

    def _subscription_retrieve(self, subscription_id: str):
        return self.subscriptions[subscription_id]

    def _subscription_modify(self, subscription_id: str, **kwargs):
        subscription = self.subscriptions[subscription_id]
        if "cancel_at_period_end" in kwargs:
            subscription["cancel_at_period_end"] = kwargs["cancel_at_period_end"]
            if not kwargs["cancel_at_period_end"]:
                subscription["status"] = "canceled"
        if "items" in kwargs:
            quantity = kwargs["items"][0]["quantity"]
            subscription["items"]["data"][0]["quantity"] = quantity
        if "metadata" in kwargs:
            subscription["metadata"] = kwargs["metadata"]
        return subscription

    def _subscription_delete(self, subscription_id: str):
        subscription = self.subscriptions[subscription_id]
        subscription["status"] = "canceled"
        subscription["cancel_at_period_end"] = False
        subscription["canceled_at"] = self._now()
        return subscription

    def _payment_intent_create(self, **kwargs):
        intent_id = self._generate_id("pi")
        # Determine status based on confirm flag and attached payment method
        pm_id = kwargs.get("payment_method")
        status = "succeeded" if kwargs.get("confirm") else "requires_payment_method"

        # If a payment method is provided, inspect its card to simulate
        # edge cases per stripe testing docs (declines, 3DS required)
        if pm_id:
            pm = self.payment_methods.get(pm_id) or {}
            card = pm.get("card") or {}
            number = card.get("number")
            # Generic decline
            if number == "4000000000000002":
                raise Exception("card_declined: The card was declined.")
            # 3DS required
            if number == "4000000000003220":
                status = "requires_action"

        payment_intent = {
            "id": intent_id,
            "amount": kwargs.get("amount"),
            "currency": kwargs.get("currency", "usd"),
            "status": status,
            "description": kwargs.get("description"),
            "payment_method": kwargs.get("payment_method"),
            "customer": kwargs.get("customer"),
            "created": self._now(),
            "metadata": kwargs.get("metadata") or {},
            **({"next_action": {"type": "use_stripe_sdk"}} if status == "requires_action" else {}),
        }
        self.payment_intents[intent_id] = payment_intent
        return payment_intent

    def _payment_intent_retrieve(self, intent_id: str):
        return self.payment_intents[intent_id]

    def _refund_create(self, **kwargs):
        refund_id = self._generate_id("re")
        payment_intent_id = kwargs["payment_intent"]
        payment_intent = self.payment_intents[payment_intent_id]
        amount = kwargs.get("amount", payment_intent["amount"])
        refund = {
            "id": refund_id,
            "payment_intent": payment_intent_id,
            "amount": amount,
            "currency": payment_intent["currency"],
            "status": "succeeded",
            "created": self._now(),
        }
        self.refunds[refund_id] = refund
        return refund

    def _usage_record_create(self, **kwargs):
        usage_id = self._generate_id("ur")
        usage_record = {
            "id": usage_id,
            "subscription_item": kwargs.get("subscription_item"),
            "quantity": kwargs.get("quantity"),
            "timestamp": kwargs.get("timestamp"),
        }
        self.usage_records[usage_id] = usage_record
        return usage_record
