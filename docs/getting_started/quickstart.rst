Quickstart
=========

Basic Integration
---------------

Integrate FastAPI Payments into your FastAPI application:

.. code-block:: python

   from fastapi import FastAPI
   from fastapi_payments import FastAPIPayments, create_payment_module
   import json
   
   # Create FastAPI app
   app = FastAPI()
   
   # Load configuration
   with open("payment_config.json") as f:
       config = json.load(f)
   
   # Initialize payments module
   payments = FastAPIPayments(config)
   
   # Include payment routes with prefix
   payments.include_router(app, prefix="/api")
   
   # Start server
   if __name__ == "__main__":
       import uvicorn
       uvicorn.run(app, host="0.0.0.0", port=8000)

Basic Operations
--------------

Creating a Customer
^^^^^^^^^^^^^^^^^

.. code-block:: python

   from fastapi import Depends
   from fastapi_payments.services.payment_service import get_payment_service, PaymentService
   
   @app.post("/create-customer")
   async def create_customer(
       email: str,
       name: str,
       payment_service: PaymentService = Depends(get_payment_service)
   ):
       customer = await payment_service.create_customer(
           email=email,
           name=name
       )
       return customer

Creating a Product and Plan
^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   @app.post("/create-product")
   async def create_product(
       name: str,
       description: str,
       payment_service: PaymentService = Depends(get_payment_service)
   ):
       # Create product
       product = await payment_service.create_product(
           name=name,
           description=description
       )
       
       # Create a subscription plan for the product
       plan = await payment_service.create_plan(
           product_id=product["id"],
           name="Monthly Plan",
           description="Monthly subscription",
           pricing_model="subscription",
           amount=19.99,
           currency="USD",
           billing_interval="month"
       )
       
       return {
           "product": product,
           "plan": plan
       }

Creating a Subscription
^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   @app.post("/subscribe/{customer_id}")
   async def create_subscription(
       customer_id: str,
       plan_id: str,
       payment_service: PaymentService = Depends(get_payment_service)
   ):
       subscription = await payment_service.create_subscription(
           customer_id=customer_id,
           plan_id=plan_id
       )
       return subscription

Processing a Payment
^^^^^^^^^^^^^^^^^

.. code-block:: python

   @app.post("/charge/{customer_id}")
   async def charge_customer(
       customer_id: str,
       amount: float,
       payment_method_id: str,
       payment_service: PaymentService = Depends(get_payment_service)
   ):
       payment = await payment_service.process_payment(
           customer_id=customer_id,
           amount=amount,
           currency="USD",
           payment_method_id=payment_method_id,
           description="One-time charge"
       )
       return payment

Handling Webhooks
^^^^^^^^^^^^^^

.. code-block:: python

   @app.post("/webhooks/{provider}")
   async def handle_webhook(
       provider: str,
       request: Request,
       payment_service: PaymentService = Depends(get_payment_service)
   ):
       payload = await request.json()
       signature = request.headers.get(f"{provider}-signature")
       
       result = await payment_service.handle_webhook(
           provider=provider,
           payload=payload,
           signature=signature
       )
       return {"status": "success"}

Complete Example
--------------

Check out a complete example application in the :doc:`../examples/simple_subscription` section.