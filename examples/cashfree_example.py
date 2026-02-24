"""
Cashfree Payment Provider Example
==================================

This example demonstrates how to use the Cashfree provider with FastAPI Payments.

Requirements:
- fastapi-payments library installed
- Cashfree account with API credentials
"""

import asyncio
from fastapi import FastAPI
from fastapi_payments import create_payment_module

# Example configuration for Cashfree
config = {
    "providers": {
        "cashfree": {
            "api_key": "your_cashfree_client_id",  # Replace with your client ID
            "api_secret": "your_cashfree_client_secret",  # Replace with your client secret
            "sandbox_mode": True,  # Set to False for production
            "additional_settings": {
                "collection_mode": "india",  # Use "global" for international payments
                "return_url": "https://yourdomain.com/payment/return",
                "notify_url": "https://yourdomain.com/webhooks/cashfree",
                "api_version": "2023-08-01"
            }
        }
    },
    "default_provider": "cashfree"
}


async def main():
    """Main example function."""
    
    # Initialize payment module
    payment_module = create_payment_module(config)
    payment_service = payment_module.payment_service
    
    print("=" * 60)
    print("Cashfree Payment Provider Example")
    print("=" * 60)
    
    # 1. Create a customer
    print("\n1. Creating customer...")
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
    print(f"✅ Customer created: {customer['provider_customer_id']}")
    
    # 2. Process a one-time payment
    print("\n2. Processing one-time payment...")
    payment = await payment_service.process_payment(
        amount=100.0,
        currency="INR",
        provider_customer_id=customer["provider_customer_id"],
        description="Test Order #12345",
        meta_info={
            "cashfree": {
                "customer_name": "John Doe",
                "customer_email": "customer@example.com",
                "customer_phone": "9999999999",
                "return_url": "https://yourdomain.com/payment/success",
                "tags": {
                    "order_reference": "ORD-12345"
                }
            }
        }
    )
    print(f"✅ Payment initiated: {payment['provider_payment_id']}")
    print(f"   Payment session ID: {payment['meta_info']['payment_session_id']}")
    print(f"   Order token: {payment['meta_info']['order_token']}")
    
    # 3. Create a product
    print("\n3. Creating product...")
    product = await payment_service.create_product(
        name="Premium Membership",
        description="Access to all premium features"
    )
    print(f"✅ Product created: {product['provider_product_id']}")
    
    # 4. Create a price/plan
    print("\n4. Creating price plan...")
    price = await payment_service.create_price(
        product_id=product["provider_product_id"],
        amount=999.0,
        currency="INR",
        interval="month",
        interval_count=1,
        meta_info={
            "name": "Monthly Premium Plan",
            "max_cycles": 12
        }
    )
    print(f"✅ Price plan created: {price['provider_price_id']}")
    
    # 5. Create a subscription
    print("\n5. Creating subscription...")
    subscription = await payment_service.create_subscription(
        provider_customer_id=customer["provider_customer_id"],
        price_id=price["provider_price_id"],
        quantity=1,
        meta_info={
            "customer_name": "John Doe",
            "customer_email": "customer@example.com",
            "customer_phone": "9999999999",
            "cashfree": {
                "first_charge_date": "2024-12-31",
                "return_url": "https://yourdomain.com/subscription/success"
            }
        }
    )
    print(f"✅ Subscription created: {subscription['provider_subscription_id']}")
    print(f"   Authorization URL: {subscription['meta_info'].get('authorization_url')}")
    
    # 6. Retrieve subscription
    print("\n6. Retrieving subscription...")
    retrieved_sub = await payment_service.retrieve_subscription(
        provider_subscription_id=subscription["provider_subscription_id"]
    )
    print(f"✅ Subscription retrieved: {retrieved_sub['status']}")
    
    # 7. Cancel subscription
    print("\n7. Canceling subscription...")
    canceled_sub = await payment_service.cancel_subscription(
        provider_subscription_id=subscription["provider_subscription_id"]
    )
    print(f"✅ Subscription canceled: {canceled_sub['status']}")
    
    print("\n" + "=" * 60)
    print("Example completed successfully!")
    print("=" * 60)


# FastAPI webhook endpoint example
app = FastAPI()


@app.post("/webhooks/cashfree")
async def cashfree_webhook(request):
    """
    Handle Cashfree webhook notifications.
    
    Cashfree sends webhooks for:
    - Payment success/failure
    - Subscription events
    - Refund events
    """
    from fastapi import Request
    
    # Get webhook payload
    payload = await request.json()
    
    # Get signature for verification
    signature = request.headers.get("x-webhook-signature")
    timestamp = request.headers.get("x-webhook-timestamp")
    
    # Initialize payment module
    payment_module = create_payment_module(config)
    
    # Verify signature (recommended for production)
    provider = payment_module.payment_service.get_provider("cashfree")
    payload_str = await request.body()
    
    if not provider._verify_webhook_signature(payload_str.decode(), signature, timestamp):
        return {"status": "error", "message": "Invalid signature"}
    
    # Process webhook
    event = await payment_module.payment_service.handle_webhook("cashfree", payload)
    
    # Handle different event types
    event_type = event["standardized_event_type"]
    
    if event_type == "payment.succeeded":
        # Handle successful payment
        print(f"Payment succeeded: {event['data']}")
        
    elif event_type == "payment.failed":
        # Handle failed payment
        print(f"Payment failed: {event['data']}")
        
    elif event_type == "subscription.created":
        # Handle subscription activation
        print(f"Subscription activated: {event['data']}")
        
    elif event_type == "subscription.payment_succeeded":
        # Handle successful subscription payment
        print(f"Subscription payment succeeded: {event['data']}")
        
    elif event_type == "subscription.canceled":
        # Handle subscription cancellation
        print(f"Subscription canceled: {event['data']}")
    
    return {"status": "success"}


if __name__ == "__main__":
    # Run the example
    asyncio.run(main())
    
    # To run the FastAPI webhook server:
    # uvicorn cashfree_example:app --reload --port 8000
