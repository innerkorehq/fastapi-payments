Webhook Handling Example
======================

This example demonstrates how to handle webhooks from different payment providers.

Setting Up Webhook Endpoints
--------------------------

First, let's define our FastAPI endpoints:

.. code-block:: python

   from fastapi import FastAPI, Request, Depends, HTTPException, Header
   from fastapi_payments import FastAPIPayments
   from fastapi_payments.services.payment_service import get_payment_service, PaymentService

   # Initialize app and payments module
   app = FastAPI(title="Webhook Handler Example")
   payments = FastAPIPayments(config)
   payments.include_router(app)

Stripe Webhooks
^^^^^^^^^^^^^

.. code-block:: python

   @app.post("/webhooks/stripe", tags=["Webhooks"])
   async def handle_stripe_webhook(
       request: Request,
       stripe_signature: str = Header(None),
       payment_service: PaymentService = Depends(get_payment_service)
   ):
       """Handle webhooks from Stripe."""
       try:
           # Get raw payload for signature verification
           payload = await request.body()
           payload_json = await request.json()
           
           result = await payment_service.handle_webhook(
               provider="stripe",
               payload=payload_json,
               signature=stripe_signature
           )
           
           # Process webhook based on event type
           event_type = result.get("event_type")
           
           if event_type == "payment_intent.succeeded":
               # Handle successful payment
               payment_id = result["data"]["object"]["id"]
               amount = result["data"]["object"]["amount"] / 100  # Convert from cents
               print(f"Payment succeeded: {payment_id} for ${amount}")
               
               # Update order status, send confirmation email, etc.
               
           elif event_type == "payment_intent.payment_failed":
               # Handle failed payment
               payment_id = result["data"]["object"]["id"]
               error_message = result["data"]["object"].get("last_payment_error", {}).get("message")
               print(f"Payment failed: {payment_id} - {error_message}")
               
               # Notify customer, retry payment, etc.
               
           elif event_type == "customer.subscription.created":
               # Handle new subscription
               subscription_id = result["data"]["object"]["id"]
               print(f"New subscription: {subscription_id}")
               
               # Provision services, send welcome email, etc.
               
           elif event_type == "customer.subscription.deleted":
               # Handle subscription cancellation
               subscription_id = result["data"]["object"]["id"]
               print(f"Subscription canceled: {subscription_id}")
               
               # Deprovision services, send goodbye email, etc.
               
           # Return success to acknowledge receipt
           return {"status": "success"}
           
       except Exception as e:
           print(f"Error processing webhook: {str(e)}")
           raise HTTPException(status_code=400, detail=str(e))

PayPal Webhooks
^^^^^^^^^^^^^

.. code-block:: python

   @app.post("/webhooks/paypal", tags=["Webhooks"])
   async def handle_paypal_webhook(
       request: Request,
       paypal_transmission_id: str = Header(None, alias="Paypal-Transmission-Id"),
       paypal_transmission_time: str = Header(None, alias="Paypal-Transmission-Time"),
       paypal_transmission_sig: str = Header(None, alias="Paypal-Transmission-Sig"),
       paypal_cert_url: str = Header(None, alias="Paypal-Cert-Url"),
       paypal_auth_algo: str = Header(None, alias="Paypal-Auth-Algo"),
       payment_service: PaymentService = Depends(get_payment_service)
   ):
       """Handle webhooks from PayPal."""
       try:
           payload = await request.json()
           
           # Collect signature information for verification
           signature = {
               "transmission_id": paypal_transmission_id,
               "transmission_time": paypal_transmission_time,
               "transmission_sig": paypal_transmission_sig,
               "cert_url": paypal_cert_url,
               "auth_algo": paypal_auth_algo
           }
           
           result = await payment_service.handle_webhook(
               provider="paypal",
               payload=payload,
               signature=signature
           )
           
           # Process webhook based on event type
           event_type = payload.get("event_type")
           
           if "PAYMENT.CAPTURE.COMPLETED" in event_type:
               # Handle completed payment
               payment_id = payload["resource"]["id"]
               amount = payload["resource"]["amount"]["value"]
               print(f"Payment completed: {payment_id} for {amount}")
               
           elif "PAYMENT.CAPTURE.DENIED" in event_type:
               # Handle denied payment
               payment_id = payload["resource"]["id"]
               print(f"Payment denied: {payment_id}")
               
           elif "BILLING.SUBSCRIPTION.CREATED" in event_type:
               # Handle subscription creation
               subscription_id = payload["resource"]["id"]
               print(f"Subscription created: {subscription_id}")
               
           elif "BILLING.SUBSCRIPTION.CANCELLED" in event_type:
               # Handle subscription cancellation
               subscription_id = payload["resource"]["id"]
               print(f"Subscription cancelled: {subscription_id}")
               
           # Return success
           return {"status": "success"}
           
       except Exception as e:
           print(f"Error processing webhook: {str(e)}")
           raise HTTPException(status_code=400, detail=str(e))

Adyen Webhooks
^^^^^^^^^^^^

.. code-block:: python

   @app.post("/webhooks/adyen", tags=["Webhooks"])
   async def handle_adyen_webhook(
       request: Request,
       payment_service: PaymentService = Depends(get_payment_service)
   ):
       """Handle webhooks from Adyen."""
       try:
           payload = await request.json()
           
           result = await payment_service.handle_webhook(
               provider="adyen",
               payload=payload
           )
           
           # Process notifications
           for item in payload.get("notificationItems", []):
               notification = item.get("NotificationRequestItem", {})
               event_code = notification.get("eventCode")
               success = notification.get("success") == "true"
               psp_reference = notification.get("pspReference")
               
               if event_code == "AUTHORISATION" and success:
                   # Handle successful authorization
                   print(f"Payment authorized: {psp_reference}")
                   
               elif event_code == "CAPTURE" and success:
                   # Handle successful capture
                   print(f"Payment captured: {psp_reference}")
                   
               elif event_code == "REFUND" and success:
                   # Handle successful refund
                   print(f"Payment refunded: {psp_reference}")
                   
               elif event_code == "CANCEL_OR_REFUND" and success:
                   # Handle cancellation or refund
                   print(f"Payment cancelled/refunded: {psp_reference}")
                   
           # Return Adyen-specific response format
           return {"notificationResponse": "success"}
           
       except Exception as e:
           print(f"Error processing webhook: {str(e)}")
           