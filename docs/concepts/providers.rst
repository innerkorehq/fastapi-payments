Payment Providers
===============

Provider Architecture
-------------------

FastAPI Payments is built around the concept of payment providers. Each provider implements a common interface defined in the ``PaymentProvider`` abstract base class, enabling you to switch providers with minimal code changes.

The Provider Interface
--------------------

Each provider implements these key methods:

Customer Management
^^^^^^^^^^^^^^^^^

- ``create_customer``: Create a customer in the provider's system
- ``retrieve_customer``: Get customer details from the provider
- ``update_customer``: Update customer details
- ``delete_customer``: Delete a customer

Payment Method Management
^^^^^^^^^^^^^^^^^^^^^^

- ``create_payment_method``: Register a payment method for a customer
- ``list_payment_methods``: List a customer's payment methods
- ``delete_payment_method``: Remove a payment method

Product and Plan Management
^^^^^^^^^^^^^^^^^^^^^^^

- ``create_product``: Create a product in the provider's system
- ``create_price``: Create a pricing plan for a product

Subscription Management
^^^^^^^^^^^^^^^^^^^^

- ``create_subscription``: Subscribe a customer to a plan
- ``retrieve_subscription``: Get subscription details
- ``update_subscription``: Update subscription details
- ``cancel_subscription``: Cancel a subscription

Payment Processing
^^^^^^^^^^^^^^^

- ``process_payment``: Process a one-time payment
- ``refund_payment``: Process a refund
- ``record_usage``: Record usage for usage-based billing

Webhook Handling
^^^^^^^^^^^^^

- ``webhook_handler``: Process webhook events from the provider

Supported Providers
-----------------

Stripe Provider
^^^^^^^^^^^^^

The Stripe provider offers comprehensive payment processing capabilities:

- Full support for Stripe API
- Credit card processing
- Subscription management
- Usage-based billing
- Webhook handling with signature verification

Example Stripe configuration:

.. code-block:: json

   {
     "providers": {
       "stripe": {
         "api_key": "sk_test_your_stripe_key",
         "webhook_secret": "whsec_your_webhook_secret",
         "sandbox_mode": true,
         "additional_settings": {
           "api_version": "2023-10-16"
         }
       }
     }
   }

PayPal Provider
^^^^^^^^^^^^^

The PayPal provider supports:

- PayPal checkout
- Credit card processing via PayPal
- Subscription billing
- Webhook handling

Example PayPal configuration:

.. code-block:: json

   {
     "providers": {
       "paypal": {
         "api_key": "your_paypal_client_id",
         "api_secret": "your_paypal_secret",
         "sandbox_mode": true
       }
     }
   }

Adyen Provider
^^^^^^^^^^^^

The Adyen provider supports:

- Global payment methods
- Credit card processing
- Tokenized payments
- Webhook notification handling

Example Adyen configuration:

.. code-block:: json

   {
     "providers": {
       "adyen": {
         "api_key": "your_adyen_api_key",
         "webhook_secret": "your_adyen_webhook_secret",
         "sandbox_mode": true,
         "additional_settings": {
           "merchant_account": "YourMerchantAccount"
         }
       }
     }
   }

Adding Custom Providers
---------------------

You can create custom providers by implementing the ``PaymentProvider`` abstract base class. See :doc:`../advanced/extending` for details.