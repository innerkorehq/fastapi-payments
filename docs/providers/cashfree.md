# Cashfree Integration Guide

Cashfree is an India-based payment gateway that supports both domestic (India) and international payments. This guide covers how to integrate Cashfree with the FastAPI Payments library.

## Features Supported

- ✅ One-time payments (Orders API)
- ✅ Subscription payments (Subscription API)
- ✅ Payment refunds
- ✅ Webhook handling
- ✅ India collections (default)
- ✅ Global collections (for international payments)

## Configuration

### Basic Configuration (India Collections)

```python
from fastapi_payments import create_payment_module

config = {
    "providers": {
        "cashfree": {
            "api_key": "your_cashfree_client_id",
            "api_secret": "your_cashfree_client_secret",
            "sandbox_mode": True,
            "additional_settings": {
                "collection_mode": "india",  # Default
                "return_url": "https://yourdomain.com/payment/return",
                "notify_url": "https://yourdomain.com/payment/webhook",
                "api_version": "2023-08-01"
            }
        }
    },
    "default_provider": "cashfree"
}

payment_module = create_payment_module(config)
```

### Global Collections Configuration

For Indian businesses collecting payments from customers worldwide:

```python
config = {
    "providers": {
        "cashfree_global": {
            "api_key": "your_cashfree_client_id",
            "api_secret": "your_cashfree_client_secret",
            "sandbox_mode": True,
            "additional_settings": {
                "collection_mode": "global",  # Enable global collections
                "return_url": "https://yourdomain.com/payment/return",
                "notify_url": "https://yourdomain.com/payment/webhook"
            }
        }
    },
    "default_provider": "cashfree_global"
}
```

## Usage Examples

### 1. Create a Customer

Cashfree doesn't have a dedicated customer object, but you can store customer data locally:

```python
customer = await payment_service.create_customer(
    email="customer@example.com",
    name="John Doe",
    meta_info={
        "phone": "9999999999"
    },
    address={
        "line1": "123 Main Street",
        "city": "Mumbai",
        "state": "Maharashtra",
        "postal_code": "400001",
        "country": "IN"
    }
)
```

**Note**: Address is required for India-based providers like Cashfree for regulatory compliance.

### 2. Process a One-Time Payment

```python
payment = await payment_service.process_payment(
    amount=100.0,
    currency="INR",
    provider_customer_id=customer["provider_customer_id"],
    description="Order #12345",
    meta_info={
        "customer_name": "John Doe",
        "customer_email": "customer@example.com",
        "customer_phone": "9999999999",
        "cashfree": {
            "order_id": "order_12345",  # Optional - auto-generated if not provided
            "return_url": "https://yourdomain.com/payment/success",
            "notify_url": "https://yourdomain.com/webhooks/cashfree",
            "tags": {
                "order_reference": "ORD-12345"
            }
        }
    }
)

# Get checkout details
payment_session_id = payment["meta_info"]["payment_session_id"]
order_token = payment["meta_info"]["order_token"]

# Use these to initialize Cashfree checkout on client side
```

### 3. Create a Subscription

#### Step 1: Create a Product

```python
product = await payment_service.create_product(
    name="Premium Membership",
    description="Access to all premium features"
)
```

#### Step 2: Create a Price/Plan

```python
price = await payment_service.create_price(
    product_id=product["provider_product_id"],
    amount=999.0,
    currency="INR",
    interval="month",
    interval_count=1,
    meta_info={
        "name": "Monthly Premium Plan",
        "max_cycles": 12  # Optional: limit to 12 months
    }
)
```

#### Step 3: Create a Subscription

```python
subscription = await payment_service.create_subscription(
    provider_customer_id=customer["provider_customer_id"],
    price_id=price["provider_price_id"],
    quantity=1,
    meta_info={
        "customer_name": "John Doe",
        "customer_email": "customer@example.com",
        "customer_phone": "9999999999",
        "cashfree": {
            "first_charge_date": "2024-01-01",  # YYYY-MM-DD format
            "expiry_date": "2024-12-31",  # Optional
            "return_url": "https://yourdomain.com/subscription/success",
            "notify_url": "https://yourdomain.com/webhooks/cashfree"
        }
    }
)

# Get authorization URL for customer to complete subscription setup
authorization_url = subscription["meta_info"]["authorization_url"]
```

### 4. Handle Webhooks

```python
from fastapi import Request

@app.post("/webhooks/cashfree")
async def cashfree_webhook(request: Request):
    # Get webhook payload
    payload = await request.json()
    
    # Get headers for signature verification
    signature = request.headers.get("x-webhook-signature")
    timestamp = request.headers.get("x-webhook-timestamp")
    
    # Verify signature (recommended)
    provider = payment_service.get_provider("cashfree")
    payload_str = await request.body()
    
    if not provider._verify_webhook_signature(payload_str.decode(), signature, timestamp):
        return {"status": "error", "message": "Invalid signature"}
    
    # Process webhook
    event = await payment_service.handle_webhook("cashfree", payload)
    
    # Handle different event types
    if event["standardized_event_type"] == "payment.succeeded":
        # Handle successful payment
        order_id = event["data"]["order"]["order_id"]
        print(f"Payment succeeded for order: {order_id}")
    
    elif event["standardized_event_type"] == "subscription.created":
        # Handle subscription activation
        subscription_id = event["data"]["subscription"]["subscription_id"]
        print(f"Subscription activated: {subscription_id}")
    
    return {"status": "success"}
```

### 5. Refund a Payment

```python
refund = await payment_service.refund_payment(
    provider_payment_id=payment["provider_payment_id"],
    amount=50.0,  # Partial refund
    meta_info={
        "cashfree": {
            "order_id": "order_12345",  # Required
            "refund_note": "Customer requested refund"
        }
    }
)
```

### 6. Manage Subscriptions

#### Retrieve Subscription

```python
subscription = await payment_service.retrieve_subscription(
    provider_subscription_id="sub_12345"
)
```

#### Cancel Subscription

```python
result = await payment_service.cancel_subscription(
    provider_subscription_id="sub_12345"
)
```

## Webhook Events

Cashfree sends the following webhook events:

| Cashfree Event | Standardized Event Type |
|----------------|-------------------------|
| PAYMENT_SUCCESS_WEBHOOK | payment.succeeded |
| PAYMENT_FAILED_WEBHOOK | payment.failed |
| PAYMENT_USER_DROPPED_WEBHOOK | payment.canceled |
| SUBSCRIPTION_ACTIVATED | subscription.created |
| SUBSCRIPTION_CHARGED_SUCCESSFULLY | subscription.payment_succeeded |
| SUBSCRIPTION_CHARGE_FAILED | subscription.payment_failed |
| SUBSCRIPTION_CANCELLED | subscription.canceled |
| SUBSCRIPTION_PAUSED | subscription.paused |
| SUBSCRIPTION_RESUMED | subscription.resumed |
| REFUND_PROCESSED | refund.succeeded |
| REFUND_FAILED | refund.failed |

## Testing

Use Cashfree's sandbox mode for testing:

```python
config = {
    "providers": {
        "cashfree": {
            "sandbox_mode": True,  # Enable test mode
            # ... other config
        }
    }
}
```

### Test Credentials

You can obtain test API credentials from the Cashfree Dashboard:
1. Sign up at [Cashfree Dashboard](https://merchant.cashfree.com/)
2. Navigate to Developers → API Keys
3. Generate test mode credentials

## Important Notes

### India Collections vs Global Collections

- **India Collections** (default): For all businesses accepting payments from Indian customers
- **Global Collections**: For Indian businesses accepting payments from international customers

Set the `collection_mode` in `additional_settings` to choose:
- `"india"` (default) - India collections
- `"global"` - Global collections

### Required Fields

#### For Payments:
- Customer name (required)
- Customer email (required)
- Customer phone (required)
- Return URL (required)

#### For Subscriptions:
- All payment fields +
- First charge date (optional but recommended)
- Notify URL for webhook notifications

### Address Requirements

For India-based providers, providing customer address is important for:
- Regulatory compliance
- Risk assessment
- Better transaction success rates

### Currency Support

- **India Collections**: INR only
- **Global Collections**: Multiple currencies supported

## API Documentation

For detailed API documentation, refer to:
- [Cashfree Payments API](https://www.cashfree.com/docs/api-reference/payments/latest)
- [Cashfree Subscriptions API](https://www.cashfree.com/docs/api-reference/payments/latest/subscription)
- [Cashfree International Payments](https://www.cashfree.com/docs/api-reference/payments/latest/international-payments)

## Support

For Cashfree-specific issues:
- Cashfree Support: https://www.cashfree.com/contact-us
- Documentation: https://www.cashfree.com/docs

For FastAPI Payments library issues:
- GitHub Issues: https://github.com/innerkorehq/fastapi-payments/issues
