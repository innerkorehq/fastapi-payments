"""Fake Razorpay provider for testing."""

from typing import Dict, Any, Optional, List
import uuid
from datetime import datetime, timezone


class FakeRazorpay:
    """Mock Razorpay API for testing.
    
    Mimics the razorpay SDK client structure.
    """
    
    def __init__(self):
        self.customers = {}
        self.plans = {}
        self.subscriptions = {}
        self.orders = {}
        self.payments = {}
        self.refunds = {}
        self.items = {}
        self.tokens = {}
        
        # Set up sub-clients
        self.customer = _FakeCustomerClient(self)
        self.plan = _FakePlanClient(self)
        self.subscription = _FakeSubscriptionClient(self)
        self.order = _FakeOrderClient(self)
        self.payment = _FakePaymentClient(self)
        self.item = _FakeItemClient(self)
        self.invoice = _FakeInvoiceClient(self)
        self.utility = _FakeUtilityClient(self)

    @staticmethod
    def _now() -> int:
        return int(datetime.now(timezone.utc).timestamp())

    @staticmethod
    def _generate_id(prefix: str) -> str:
        return f"{prefix}_{uuid.uuid4().hex[:14]}"


class _FakeCustomerClient:
    """Mock Razorpay customer client."""
    
    def __init__(self, parent: FakeRazorpay):
        self._parent = parent

    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a customer."""
        customer_id = FakeRazorpay._generate_id("cust")
        customer = {
            "id": customer_id,
            "name": data.get("name"),
            "email": data.get("email"),
            "contact": data.get("contact"),
            "gstin": data.get("gstin"),
            "notes": data.get("notes", {}),
            "created_at": FakeRazorpay._now(),
        }
        self._parent.customers[customer_id] = customer
        return customer

    def fetch(self, customer_id: str) -> Dict[str, Any]:
        """Fetch a customer."""
        if customer_id not in self._parent.customers:
            raise Exception(f"Customer {customer_id} not found")
        return self._parent.customers[customer_id]

    def edit(self, customer_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Edit a customer."""
        if customer_id not in self._parent.customers:
            raise Exception(f"Customer {customer_id} not found")
        customer = self._parent.customers[customer_id]
        customer.update({k: v for k, v in data.items() if v is not None})
        return customer

    def fetchTokens(self, customer_id: str) -> Dict[str, Any]:
        """Fetch tokens for a customer."""
        tokens = [t for t in self._parent.tokens.values() 
                  if t.get("customer_id") == customer_id]
        return {"items": tokens}


class _FakePlanClient:
    """Mock Razorpay plan client."""
    
    def __init__(self, parent: FakeRazorpay):
        self._parent = parent

    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a plan."""
        plan_id = FakeRazorpay._generate_id("plan")
        item = data.get("item", {})
        plan = {
            "id": plan_id,
            "period": data.get("period", "monthly"),
            "interval": data.get("interval", 1),
            "item": {
                "id": FakeRazorpay._generate_id("item"),
                "name": item.get("name"),
                "amount": item.get("amount"),
                "currency": item.get("currency", "INR"),
                "description": item.get("description"),
            },
            "notes": data.get("notes", {}),
            "created_at": FakeRazorpay._now(),
        }
        self._parent.plans[plan_id] = plan
        return plan

    def fetch(self, plan_id: str) -> Dict[str, Any]:
        """Fetch a plan."""
        if plan_id not in self._parent.plans:
            raise Exception(f"Plan {plan_id} not found")
        return self._parent.plans[plan_id]

    def all(self, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Fetch all plans."""
        plans = list(self._parent.plans.values())
        return {"items": plans, "count": len(plans)}


class _FakeSubscriptionClient:
    """Mock Razorpay subscription client."""
    
    def __init__(self, parent: FakeRazorpay):
        self._parent = parent

    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a subscription."""
        subscription_id = FakeRazorpay._generate_id("sub")
        now = FakeRazorpay._now()
        # 30 days later
        period_end = now + 30 * 24 * 60 * 60
        
        subscription = {
            "id": subscription_id,
            "plan_id": data.get("plan_id"),
            "customer_id": data.get("customer_id"),
            "status": "created",
            "quantity": data.get("quantity", 1),
            "total_count": data.get("total_count", 12),
            "paid_count": 0,
            "remaining_count": data.get("total_count", 12),
            "current_start": now,
            "current_end": period_end,
            "charge_at": period_end,
            "customer_notify": data.get("customer_notify", 1),
            "notes": data.get("notes", {}),
            "short_url": f"https://rzp.io/i/{subscription_id[:8]}",
            "created_at": now,
        }
        
        if "start_at" in data:
            subscription["start_at"] = data["start_at"]
        if "expire_by" in data:
            subscription["expire_by"] = data["expire_by"]
        if "offer_id" in data:
            subscription["offer_id"] = data["offer_id"]
        
        self._parent.subscriptions[subscription_id] = subscription
        return subscription

    def fetch(self, subscription_id: str) -> Dict[str, Any]:
        """Fetch a subscription."""
        if subscription_id not in self._parent.subscriptions:
            raise Exception(f"Subscription {subscription_id} not found")
        return self._parent.subscriptions[subscription_id]

    def update(self, subscription_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update a subscription."""
        if subscription_id not in self._parent.subscriptions:
            raise Exception(f"Subscription {subscription_id} not found")
        subscription = self._parent.subscriptions[subscription_id]
        
        if "plan_id" in data:
            subscription["plan_id"] = data["plan_id"]
        if "quantity" in data:
            subscription["quantity"] = data["quantity"]
        if "offer_id" in data:
            subscription["offer_id"] = data["offer_id"]
        if "customer_notify" in data:
            subscription["customer_notify"] = data["customer_notify"]
        
        return subscription

    def cancel(self, subscription_id: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Cancel a subscription."""
        if subscription_id not in self._parent.subscriptions:
            raise Exception(f"Subscription {subscription_id} not found")
        
        subscription = self._parent.subscriptions[subscription_id]
        data = data or {}
        
        if data.get("cancel_at_cycle_end", 1) == 0:
            subscription["status"] = "cancelled"
            subscription["ended_at"] = FakeRazorpay._now()
        else:
            subscription["status"] = "cancelled"
            subscription["ended_at"] = subscription.get("current_end")
        
        return subscription

    def pause(self, subscription_id: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Pause a subscription."""
        if subscription_id not in self._parent.subscriptions:
            raise Exception(f"Subscription {subscription_id} not found")
        
        subscription = self._parent.subscriptions[subscription_id]
        subscription["status"] = "paused"
        subscription["paused_at"] = FakeRazorpay._now()
        return subscription

    def resume(self, subscription_id: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Resume a subscription."""
        if subscription_id not in self._parent.subscriptions:
            raise Exception(f"Subscription {subscription_id} not found")
        
        subscription = self._parent.subscriptions[subscription_id]
        subscription["status"] = "active"
        subscription.pop("paused_at", None)
        return subscription

    def fetch_all_invoices(self, subscription_id: str) -> Dict[str, Any]:
        """Fetch all invoices for a subscription."""
        # Return mock invoices
        return {"items": [], "count": 0}

    def pending_update(self, subscription_id: str) -> Dict[str, Any]:
        """Attempt pending update/charge."""
        if subscription_id not in self._parent.subscriptions:
            raise Exception(f"Subscription {subscription_id} not found")
        return self._parent.subscriptions[subscription_id]


class _FakeOrderClient:
    """Mock Razorpay order client."""
    
    def __init__(self, parent: FakeRazorpay):
        self._parent = parent

    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create an order."""
        order_id = FakeRazorpay._generate_id("order")
        order = {
            "id": order_id,
            "amount": data.get("amount"),
            "currency": data.get("currency", "INR"),
            "receipt": data.get("receipt"),
            "status": "created",
            "notes": data.get("notes", {}),
            "created_at": FakeRazorpay._now(),
        }
        self._parent.orders[order_id] = order
        return order

    def fetch(self, order_id: str) -> Dict[str, Any]:
        """Fetch an order."""
        if order_id not in self._parent.orders:
            raise Exception(f"Order {order_id} not found")
        return self._parent.orders[order_id]


class _FakePaymentClient:
    """Mock Razorpay payment client."""
    
    def __init__(self, parent: FakeRazorpay):
        self._parent = parent

    def fetch(self, payment_id: str) -> Dict[str, Any]:
        """Fetch a payment."""
        if payment_id not in self._parent.payments:
            # Create a mock payment for testing
            return {
                "id": payment_id,
                "amount": 10000,
                "currency": "INR",
                "status": "captured",
                "order_id": None,
                "created_at": FakeRazorpay._now(),
            }
        return self._parent.payments[payment_id]

    def refund(self, payment_id: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Refund a payment."""
        data = data or {}
        payment = self.fetch(payment_id)
        
        refund_id = FakeRazorpay._generate_id("rfnd")
        refund = {
            "id": refund_id,
            "payment_id": payment_id,
            "amount": data.get("amount", payment.get("amount")),
            "currency": payment.get("currency", "INR"),
            "status": "processed",
            "created_at": FakeRazorpay._now(),
        }
        self._parent.refunds[refund_id] = refund
        return refund


class _FakeItemClient:
    """Mock Razorpay item client."""
    
    def __init__(self, parent: FakeRazorpay):
        self._parent = parent

    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create an item."""
        item_id = FakeRazorpay._generate_id("item")
        item = {
            "id": item_id,
            "name": data.get("name"),
            "description": data.get("description"),
            "amount": data.get("amount", 0),
            "currency": data.get("currency", "INR"),
            "active": True,
            "created_at": FakeRazorpay._now(),
        }
        self._parent.items[item_id] = item
        return item

    def fetch(self, item_id: str) -> Dict[str, Any]:
        """Fetch an item."""
        if item_id not in self._parent.items:
            raise Exception(f"Item {item_id} not found")
        return self._parent.items[item_id]


class _FakeInvoiceClient:
    """Mock Razorpay invoice client."""
    
    def __init__(self, parent: FakeRazorpay):
        self._parent = parent

    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create an invoice/registration link."""
        invoice_id = FakeRazorpay._generate_id("inv")
        invoice = {
            "id": invoice_id,
            "type": data.get("type"),
            "amount": data.get("amount"),
            "currency": data.get("currency", "INR"),
            "description": data.get("description"),
            "status": "issued",
            "short_url": f"https://rzp.io/i/{invoice_id[:8]}",
            "created_at": FakeRazorpay._now(),
        }
        return invoice


class _FakeUtilityClient:
    """Mock Razorpay utility client."""
    
    def __init__(self, parent: FakeRazorpay):
        self._parent = parent

    def verify_webhook_signature(
        self, body: str, signature: str, secret: str
    ) -> bool:
        """Verify webhook signature (always returns True in fake)."""
        # For testing, always return True
        # In real tests, you can override this behavior
        return True

    def verify_payment_signature(self, params: Dict[str, Any]) -> bool:
        """Verify payment signature."""
        return True
