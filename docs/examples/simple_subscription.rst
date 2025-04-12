Simple Subscription Example
=========================

This example demonstrates how to implement a basic subscription service using FastAPI Payments.

Application Setup
---------------

First, let's set up the FastAPI application:

.. code-block:: python

   import os
   from fastapi import FastAPI, Depends, HTTPException, Request
   from pydantic import BaseModel
   import json
   from fastapi_payments import FastAPIPayments
   from fastapi_payments.services.payment_service import get_payment_service, PaymentService

   # Create FastAPI app
   app = FastAPI(title="Subscription Service")

   # Load configuration
   config_path = os.environ.get("CONFIG_PATH", "payment_config.json")
   with open(config_path) as f:
       config = json.load(f)

   # Initialize payments module
   payments = FastAPIPayments(config)

   # Include payment routes
   payments.include_router(app, prefix="/api")

Data Models
----------

Define our API request and response models:

.. code-block:: python

   class CustomerCreate(BaseModel):
       email: str
       name: str

   class SubscriptionCreate(BaseModel):
       plan_id: str
       payment_method_token: str

   class PaymentMethodCreate(BaseModel):
       token: str
       set_default: bool = True

   class WebhookRequest(BaseModel):
       payload: dict

Endpoints
--------

Now, let's implement the subscription flow:

Create Customer
^^^^^^^^^^^^^

.. code-block:: python

   @app.post("/customers", tags=["Customers"])
   async def create_customer(
       customer: CustomerCreate,
       payment_service: PaymentService = Depends(get_payment_service)
   ):
       """Create a new customer."""
       try:
           result = await payment_service.create_customer(
               email=customer.email,
               name=customer.name
           )
           return result
       except Exception as e:
           raise HTTPException(status_code=400, detail=str(e))

Add Payment Method
^^^^^^^^^^^^^^^

.. code-block:: python

   @app.post("/customers/{customer_id}/payment-methods", tags=["Payment Methods"])
   async def create_payment_method(
       customer_id: str,
       payment_method: PaymentMethodCreate,
       payment_service: PaymentService = Depends(get_payment_service)
   ):
       """Add a payment method to a customer."""
       try:
           result = await payment_service.create_payment_method(
               customer_id=customer_id,
               payment_details={
                   "type": "card",
                   "token": payment_method.token,
                   "set_default": payment_method.set_default
               }
           )
           return result
       except Exception as e:
           raise HTTPException(status_code=400, detail=str(e))

List Available Plans
^^^^^^^^^^^^^^^^^

.. code-block:: python

   @app.get("/plans", tags=["Plans"])
   async def list_plans(
       payment_service: PaymentService = Depends(get_payment_service)
   ):
       """List available subscription plans."""
       try:
           # In a real application, you'd query your database
           # This is a simplified example
           plans = [
               {
                   "id": "plan_basic",
                   "name": "Basic Plan",
                   "description": "Basic features",
                   "amount": 9.99,
                   "currency": "USD",
                   "interval": "month"
               },
               {
                   "id": "plan_premium",
                   "name": "Premium Plan",
                   "description": "Premium features",
                   "amount": 19.99,
                   "currency": "USD",
                   "interval": "month"
               },
               {
                   "id": "plan_enterprise",
                   "name": "Enterprise Plan",
                   "description": "Enterprise features",
                   "amount": 49.99,
                   "currency": "USD",
                   "interval": "month"
               }
           ]
           return plans
       except Exception as e:
           raise HTTPException(status_code=400, detail=str(e))

Create Subscription
^^^^^^^^^^^^^^^^^

.. code-block:: python

   @app.post("/customers/{customer_id}/subscriptions", tags=["Subscriptions"])
   async def create_subscription(
       customer_id: str,
       subscription: SubscriptionCreate,
       payment_service: PaymentService = Depends(get_payment_service)
   ):
       """Subscribe a customer to a plan."""
       try:
           # Add payment method if provided
           if subscription.payment_method_token:
               await payment_service.create_payment_method(
                   customer_id=customer_id,
                   payment_details={
                       "type": "card",
                       "token": subscription.payment_method_token,
                       "set_default": True
                   }
               )
           
           # Create the subscription
           result = await payment_service.create_subscription(
               customer_id=customer_id,
               plan_id=subscription.plan_id
           )
           return result
       except Exception as e:
           raise HTTPException(status_code=400, detail=str(e))

Get Subscription
^^^^^^^^^^^^^^

.. code-block:: python

   @app.get("/subscriptions/{subscription_id}", tags=["Subscriptions"])
   async def get_subscription(
       subscription_id: str,
       payment_service: PaymentService = Depends(get_payment_service)
   ):
       """Get details of a subscription."""
       try:
           result = await payment_service.get_subscription(subscription_id)
           if not result:
               raise HTTPException(status_code=404, detail="Subscription not found")
           return result
       except HTTPException:
           raise
       except Exception as e:
           raise HTTPException(status_code=400, detail=str(e))

Cancel Subscription
^^^^^^^^^^^^^^^^

.. code-block:: python

   @app.post("/subscriptions/{subscription_id}/cancel", tags=["Subscriptions"])
   async def cancel_subscription(
       subscription_id: str,
       cancel_at_period_end: bool = True,
       payment_service: PaymentService = Depends(get_payment_service)
   ):
       """Cancel a subscription."""
       try:
           result = await payment_service.cancel_subscription(
               subscription_id=subscription_id,
               cancel_at_period_end=cancel_at_period_end
           )
           return result
       except Exception as e:
           raise HTTPException(status_code=400, detail=str(e))

Handle Webhooks
^^^^^^^^^^^^^

.. code-block:: python

   @app.post("/webhooks/{provider}", tags=["Webhooks"])
   async def handle_webhook(
       provider: str,
       request: Request,
       payment_service: PaymentService = Depends(get_payment_service)
   ):
       """Handle webhooks from payment providers."""
       try:
           payload = await request.json()
           signature = request.headers.get(f"{provider}-signature")
           
           result = await payment_service.handle_webhook(
               provider=provider,
               payload=payload,
               signature=signature
           )
           
           return {"status": "success"}
       except Exception as e:
           raise HTTPException(status_code=400, detail=str(e))

Running the Application
--------------------

.. code-block:: python

   if __name__ == "__main__":
       import uvicorn
       uvicorn.run(app, host="0.0.0.0", port=8000)

Testing the Subscription Flow
--------------------------

1. Create a customer:

   .. code-block:: bash
   
      curl -X POST http://localhost:8000/customers -H "Content-Type: application/json" -d '{"email": "customer@example.com", "name": "John Doe"}'

2. Add a payment method using a test token:

   .. code-block:: bash
   
      curl -X POST http://localhost:8000/customers/{customer_id}/payment-methods -H "Content-Type: application/json" -d '{"token": "tok_visa"}'

3. Create a subscription:

   .. code-block:: bash
   
      curl -X POST http://localhost:8000/customers/{customer_id}/subscriptions -H "Content-Type: application/json" -d '{"plan_id": "plan_basic"}'

4. Get subscription details:

   .. code-block:: bash
   
      curl http://localhost:8000/subscriptions/{subscription_id}

5. Cancel the subscription:

   .. code-block:: bash
   
      curl -X POST http://localhost:8000/subscriptions/{subscription_id}/cancel