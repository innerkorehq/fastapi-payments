"""Fake Cashfree provider for testing."""

from typing import Dict, Any, Optional
import uuid
from datetime import datetime, timezone


class FakeCashfree:
    """Mock Cashfree API for testing."""
    
    def __init__(self):
        self.orders = {}
        self.subscriptions = {}
        self.plans = {}
        self.refunds = {}
    
    def create_order(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a fake order."""
        order_id = order_data["order_id"]
        payment_session_id = f"session_{uuid.uuid4().hex[:20]}"
        order_token = f"token_{uuid.uuid4().hex[:40]}"
        
        order = {
            "cf_order_id": order_id,
            "order_id": order_id,
            "order_amount": order_data["order_amount"],
            "order_currency": order_data["order_currency"],
            "order_status": "ACTIVE",
            "payment_session_id": payment_session_id,
            "order_token": order_token,
            "order_expiry_time": "2024-12-31T23:59:59+05:30",
            "customer_details": order_data["customer_details"],
        }
        
        self.orders[order_id] = order
        return order
    
    def get_order(self, order_id: str) -> Dict[str, Any]:
        """Get order details."""
        if order_id not in self.orders:
            raise ValueError(f"Order {order_id} not found")
        return self.orders[order_id]
    
    def create_plan(self, plan_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a fake subscription plan."""
        plan_id = plan_data["plan_id"]
        
        plan = {
            "plan_id": plan_id,
            "plan_name": plan_data["plan_name"],
            "plan_type": plan_data["plan_type"],
            "plan_currency": plan_data["plan_currency"],
            "plan_amount": plan_data["plan_amount"],
            "plan_interval_type": plan_data["plan_interval_type"],
            "plan_intervals": plan_data["plan_intervals"],
            "plan_status": "ACTIVE",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        
        if "plan_max_cycles" in plan_data:
            plan["plan_max_cycles"] = plan_data["plan_max_cycles"]
        if "plan_max_amount" in plan_data:
            plan["plan_max_amount"] = plan_data["plan_max_amount"]
        
        self.plans[plan_id] = plan
        return plan
    
    def create_subscription(self, subscription_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a fake subscription."""
        subscription_id = subscription_data["subscription_id"]
        
        subscription = {
            "subscription_id": subscription_id,
            "plan_id": subscription_data["plan_id"],
            "status": "INITIALIZED",
            "authorization_url": f"https://payments-test.cashfree.com/subscription/{subscription_id}",
            "subscription_customer_details": subscription_data["subscription_customer_details"],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        
        if "subscription_first_charge_date" in subscription_data:
            subscription["subscription_first_charge_date"] = subscription_data[
                "subscription_first_charge_date"
            ]
        if "subscription_expiry_date" in subscription_data:
            subscription["subscription_expiry_date"] = subscription_data[
                "subscription_expiry_date"
            ]
        
        self.subscriptions[subscription_id] = subscription
        return subscription
    
    def get_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """Get subscription details."""
        if subscription_id not in self.subscriptions:
            raise ValueError(f"Subscription {subscription_id} not found")
        return self.subscriptions[subscription_id]
    
    def cancel_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """Cancel a subscription."""
        if subscription_id not in self.subscriptions:
            raise ValueError(f"Subscription {subscription_id} not found")
        
        self.subscriptions[subscription_id]["status"] = "CANCELLED"
        self.subscriptions[subscription_id]["cancelled_at"] = datetime.now(
            timezone.utc
        ).isoformat()
        
        return self.subscriptions[subscription_id]
    
    def create_refund(
        self, order_id: str, refund_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a fake refund."""
        if order_id not in self.orders:
            raise ValueError(f"Order {order_id} not found")
        
        refund_id = refund_data["refund_id"]
        
        refund = {
            "cf_refund_id": f"cf_{refund_id}",
            "refund_id": refund_id,
            "order_id": order_id,
            "refund_amount": refund_data.get("refund_amount"),
            "refund_status": "SUCCESS",
            "refund_note": refund_data.get("refund_note"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        
        self.refunds[refund_id] = refund
        return refund
    
    def simulate_webhook(
        self, event_type: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Simulate a webhook event."""
        return {
            "type": event_type,
            "event_id": f"evt_{uuid.uuid4().hex[:12]}",
            "event_time": datetime.now(timezone.utc).isoformat(),
            "data": data,
        }
