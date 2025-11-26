# Work in Progress (Not ready for usage)

# FastAPI Payments Library

A flexible and extensible payment library for FastAPI applications supporting multiple payment providers and pricing models.

## Features

- **Multiple Payment Providers**: Support for Stripe, PayPal, Adyen, **PayU hosted checkout**, and more
- **Flexible Pricing Models**: 
  - Subscription
  - Usage-based
  - Tiered pricing
  - Per-user/seat pricing
  - Freemium
  - Dynamic pricing
  - Hybrid models
- **Asynchronous Architecture**: Built on FastAPI and SQLAlchemy 2.0 with async support
- **Event-Driven**: RabbitMQ integration via FastStream for reliable payment event messaging
- **Highly Configurable**: Extensive configuration options to customize for your needs
- **Extensible**: Easy to add new payment providers or custom pricing models

## Provider Functionality Status

| Provider | Customer | Products | Plans | Payments & Subscription |
|----------|----------|----------|-------|-------------------------|
| Stripe   | ✅       | ✅       | ✅    | ✅                     |
| PayPal   | ⚠️       | ❌       | ❌    | ❌                     |
| Adyen    | ❌       | ❌       | ❌    | ❌                      |
| PayU     | ⚠️       | ⚠️       | ⚠️    | ✅                      |

## Provider Pricing Model Completion

| Provider | Subscription | Usage-based | Tiered pricing | Per-user/seat pricing | Freemium | Dynamic pricing | Hybrid models |
|----------|--------------|-------------|----------------|-----------------------|----------|-----------------|---------------|
| Stripe   | ✅           | ❌          | ❌             | ❌                    | ❌       | ❌             | ❌            |
| PayPal   | ⚠️           | ❌          | ❌             | ❌                    | ❌       | ❌              | ❌            |
| Adyen    | ❌           | ❌          | ❌             | ❌                    | ❌       | ❌              | ❌            |
| PayU     | ⚠️           | ❌          | ❌             | ❌                    | ❌       | ❌              | ❌            |

## Installation

```bash
pip install fastapi-payments
```

## Quick Start

```python
from fastapi import FastAPI
from fastapi_payments import FastAPIPayments, create_payment_module
import json

# Create FastAPI app
app = FastAPI()

# Load payment configuration
with open("config/payment_config.json") as f:
    config = json.load(f)

# Initialize payments module
payments = FastAPIPayments(config)

# Include payment routes
payments.include_router(app, prefix="/api")

# Start server
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

## Configuration

Create a `payment_config.json` file:

```json
{
  "providers": {
    "stripe": {
      "api_key": "sk_test_your_stripe_key",
      "webhook_secret": "whsec_your_webhook_secret",
      "sandbox_mode": true
    }
  },
  "database": {
    "url": "postgresql+asyncpg://user:password@localhost/payments"
  },
  "rabbitmq": {
    "url": "amqp://guest:guest@localhost/"
  },
  "pricing": {
    "default_currency": "USD",
    "default_pricing_model": "subscription"
  },
  "default_provider": "stripe"
}
```

### PayU Hosted Checkout

To enable PayU hosted checkout add a `payu` provider:

```json
"providers": {
  "payu": {
    "api_key": "your_merchant_key",
    "api_secret": "your_merchant_salt",
    "sandbox_mode": true,
    "additional_settings": {
      "success_url": "https://merchant.test/payu/success",
      "failure_url": "https://merchant.test/payu/failure",
      "cancel_url": "https://merchant.test/payu/cancel"
    }
  }
}
```

When calling `POST /payments` include the hosted checkout fields inside `meta_info` so the library can prepare the HTML form payload:

```json
{
  "customer_id": "cust_123",
  "amount": 10.0,
  "currency": "INR",
  "meta_info": {
    "payu": {
      "firstname": "John",
      "email": "john@example.com",
      "phone": "9999999999",
      "productinfo": "Order #1001",
      "surl": "https://merchant.test/payu/success",
      "furl": "https://merchant.test/payu/failure"
    }
  }
}
```

The payment response includes `meta_info.provider_data.payu.redirect` containing the action URL and signed fields for rendering the hosted form. Webhooks posted by PayU can be sent using either JSON or form-encoded bodies and are verified automatically via the published hash logic.

## Documentation

For complete documentation, visit [https://fastapi-payments.readthedocs.io/](https://fastapi-payments.readthedocs.io/)

## Example Project
Example project implements payment processing functionality using FastAPI.

It provides endpoints for handling payment transactions, including creation,
processing, and status checking. The implementation supports various payment
providers and includes error handling and logging.

For a complete example project demonstrating payment integration with FastAPI,
refer to: https://github.com/innerkorehq/fastapi-payments-example

Usage:
  - Import the necessary classes and functions.
  - Configure payment provider settings.
  - Use the provided endpoints in your FastAPI application.

"""
## License

MIT