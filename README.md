# Work in Progress (Not ready for usage)

# FastAPI Payments Library

A flexible and extensible payment library for FastAPI applications supporting multiple payment providers and pricing models.

## Features

- **Multiple Payment Providers**: Support for Stripe, PayPal, Adyen, and more
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

## Documentation

For complete documentation, visit [https://fastapi-payments.readthedocs.io/](https://fastapi-payments.readthedocs.io/)

## License

MIT