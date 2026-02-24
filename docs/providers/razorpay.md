# Razorpay Provider

The Razorpay provider enables subscription and payment processing through [Razorpay](https://razorpay.com/), one of India's leading payment gateways.

## Features

- **Customer Management**: Create, retrieve, update customers
- **Subscription Plans**: Create recurring billing plans with flexible intervals
- **Subscriptions**: Full subscription lifecycle management including pause/resume
- **One-time Payments**: Process payments via Razorpay Orders
- **Refunds**: Full and partial refunds
- **Webhooks**: Signature-verified webhook handling

## Installation

```bash
pip install razorpay
```

## Configuration

```python
from fastapi_payments import FastAPIPayments, PaymentConfig, ProviderConfig

config = PaymentConfig(
    providers={
        "razorpay": ProviderConfig(
            api_key="rzp_test_xxxxxxxxxxxx",  # Key ID
            api_secret="your_key_secret",      # Key Secret
            webhook_secret="your_webhook_secret",
            sandbox_mode=True,
            additional_settings={
                "default_currency": "INR",
                "return_url": "https://yoursite.com/payment/success",
                "notify_url": "https://yoursite.com/webhooks/razorpay",
            }
        )
    },
    default_provider="razorpay"
)

payments = FastAPIPayments(config)
```

## Usage Examples

### Creating a Customer

```python
customer = await payments.create_customer(
    email="customer@example.com",
    name="John Doe",
    meta_info={
        "phone": "9876543210",  # Required for many Razorpay operations
    }
)
```

### Creating a Subscription Plan

```python
# First create a product (optional, for organization)
product = await payments.create_product(
    name="Premium Plan",
    description="Monthly premium subscription"
)

# Create a recurring price/plan
plan = await payments.create_price(
    product_id=product["provider_product_id"],
    amount=999.0,  # Amount in INR
    currency="INR",
    interval="month",
    interval_count=1,
    meta_info={
        "name": "Monthly Premium Plan",
        "description": "Access to all premium features"
    }
)
```

### Creating a Subscription

```python
subscription = await payments.create_subscription(
    provider_customer_id=customer["provider_customer_id"],
    price_id=plan["provider_price_id"],
    quantity=1,
    meta_info={
        "total_count": 12,  # Total billing cycles
        "customer_notify": 1,  # Notify customer via email/SMS
        # Optional: Razorpay-specific options
        "razorpay": {
            "offer_id": "offer_xxxx",  # Apply an offer
            "start_at": 1735689600,  # Unix timestamp for start
        }
    }
)

# The response includes an authorization link
auth_link = subscription["meta_info"]["short_url"]
# Redirect customer to auth_link to authorize the subscription
```

### Managing Subscriptions

```python
# Retrieve subscription
sub = await payments.retrieve_subscription(subscription["provider_subscription_id"])

# Update subscription (e.g., change quantity)
updated = await payments.update_subscription(
    subscription["provider_subscription_id"],
    {"quantity": 2}
)

# Pause subscription
provider = payments.get_provider("razorpay")
paused = await provider.pause_subscription(
    subscription["provider_subscription_id"]
)

# Resume subscription
resumed = await provider.resume_subscription(
    subscription["provider_subscription_id"]
)

# Cancel subscription at period end
cancelled = await payments.cancel_subscription(
    subscription["provider_subscription_id"],
    cancel_at_period_end=True
)

# Cancel immediately
cancelled = await payments.cancel_subscription(
    subscription["provider_subscription_id"],
    cancel_at_period_end=False
)
```

### Processing One-time Payments

```python
# Create a Razorpay Order
order = await payments.process_payment(
    amount=500.0,
    currency="INR",
    description="Product purchase",
    meta_info={
        "receipt": "order_rcpt_123",
        "product_id": "prod_xyz"
    }
)

# Use the order_id with Razorpay Checkout on frontend
order_id = order["meta_info"]["order_id"]
```

### Handling Refunds

```python
# Full refund
refund = await payments.refund_payment(
    provider_payment_id="pay_xxxxxxxx"  # Payment ID, not Order ID
)

# Partial refund
refund = await payments.refund_payment(
    provider_payment_id="pay_xxxxxxxx",
    amount=100.0  # Refund 100 INR
)
```

### Webhook Handling

```python
from fastapi import Request, Header

@app.post("/webhooks/razorpay")
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: str = Header(None)
):
    payload = await request.body()
    
    event = await payments.handle_webhook(
        provider="razorpay",
        payload=payload,
        signature=x_razorpay_signature
    )
    
    # Handle standardized events
    if event["standardized_event_type"] == "subscription.created":
        # Subscription activated
        pass
    elif event["standardized_event_type"] == "payment.succeeded":
        # Payment successful
        pass
    elif event["standardized_event_type"] == "subscription.canceled":
        # Subscription cancelled
        pass
    
    return {"status": "ok"}
```

## Subscription Lifecycle

Razorpay subscriptions follow this lifecycle:

1. **created** → Subscription created, awaiting authorization
2. **authenticated** → Customer authorized, awaiting first charge
3. **active** → Subscription is active and charging
4. **pending** → Payment pending (retry will happen)
5. **halted** → Multiple payment failures
6. **paused** → Manually paused
7. **cancelled** → Subscription cancelled
8. **completed** → All billing cycles completed
9. **expired** → Subscription expired

## Status Mapping

| Razorpay Status | Normalized Status |
|-----------------|-------------------|
| created | incomplete |
| authenticated | incomplete |
| active | active |
| pending | past_due |
| halted | past_due |
| cancelled | canceled |
| completed | canceled |
| expired | canceled |
| paused | paused |

## Event Mapping

| Razorpay Event | Standardized Event |
|----------------|-------------------|
| payment.authorized | payment.succeeded |
| payment.captured | payment.succeeded |
| payment.failed | payment.failed |
| subscription.activated | subscription.created |
| subscription.charged | invoice.payment_succeeded |
| subscription.cancelled | subscription.canceled |
| refund.processed | payment.refunded |

## Testing

Use Razorpay's test mode with test credentials:
- Test Key ID: `rzp_test_xxxxxxxxxxxx`
- Test Key Secret: Your test secret

Test cards:
- Success: `4111 1111 1111 1111`
- Failure: `4000 0000 0000 0002`

For UPI testing, use: `success@razorpay` or `failure@razorpay`

## Notes

- **Currency**: Razorpay primarily supports INR. All amounts are handled in the smallest unit (paise).
- **Phone Required**: Many Razorpay operations require a customer phone number.
- **Authorization**: Subscriptions require customer authorization via the `short_url` before they become active.
- **Webhooks**: Configure webhooks in Razorpay Dashboard → Settings → Webhooks
