Configuration
============

Configuration File
----------------

Create a JSON configuration file (e.g., ``payment_config.json``):

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
       },
       "paypal": {
         "api_key": "your_paypal_client_id",
         "api_secret": "your_paypal_secret",
         "sandbox_mode": true
       }
     },
     "database": {
       "url": "postgresql+asyncpg://user:password@localhost/payments",
       "echo": false,
       "pool_size": 5,
       "max_overflow": 10
     },
     "rabbitmq": {
       "url": "amqp://guest:guest@localhost/",
       "exchange": "payments",
       "queue_prefix": "payment_",
       "consumer_count": 2,
       "prefetch_count": 10
     },
     "pricing": {
       "default_currency": "USD",
       "default_pricing_model": "subscription",
       "round_to_decimal_places": 2,
       "tax": {
         "default_rate": 0.0,
         "included_in_price": false
       }
     },
     "default_provider": "stripe",
     "logging_level": "INFO"
   }

Environment Variables
------------------

You can also configure the library using environment variables:

.. code-block:: bash

   # Default provider
   export PAYMENT_DEFAULT_PROVIDER=stripe
   
   # Stripe configuration
   export PAYMENT_PROVIDERS__STRIPE__API_KEY=sk_test_your_key
   export PAYMENT_PROVIDERS__STRIPE__SANDBOX_MODE=true
   
   # Database configuration
   export PAYMENT_DATABASE__URL=postgresql+asyncpg://user:password@localhost/payments
   
   # RabbitMQ configuration
   export PAYMENT_RABBITMQ__URL=amqp://guest:guest@localhost/

Configuration Schema
-----------------

The full configuration schema includes:

**Provider Configuration**:

- ``api_key``: API key for the provider
- ``api_secret``: API secret (if required)
- ``sandbox_mode``: Boolean indicating test/sandbox mode
- ``webhook_secret``: Secret for webhook signature verification
- ``additional_settings``: Provider-specific additional settings

**Database Configuration**:

- ``url``: Database connection URL
- ``echo``: Enable SQL query logging
- ``pool_size``: Connection pool size
- ``max_overflow``: Maximum number of connections

**RabbitMQ Configuration**:

- ``url``: RabbitMQ connection URL
- ``exchange``: Exchange name
- ``queue_prefix``: Prefix for queue names
- ``consumer_count``: Number of consumers to run
- ``prefetch_count``: Number of messages to prefetch

**Pricing Configuration**:

- ``default_currency``: Default currency for pricing
- ``default_pricing_model``: Default pricing model
- ``round_to_decimal_places``: Number of decimal places for rounding
- ``tax``: Tax configuration

**General Settings**:

- ``default_provider``: Default payment provider
- ``retry_attempts``: Number of retry attempts for API calls
- ``retry_delay``: Delay between retries (seconds)
- ``logging_level``: Logging level (DEBUG, INFO, WARNING, ERROR)


Message Broker Configuration
-------------------------

Configure the message broker for event-driven architecture. FastAPI Payments supports multiple message brokers:

**RabbitMQ (Default)**:

.. code-block:: json

   "messaging": {
     "broker_type": "rabbitmq",
     "url": "amqp://guest:guest@localhost/",
     "exchange_name": "payments",
     "queue_prefix": "payment_",
     "consumer_count": 2,
     "exchange_type": "topic",
     "exchange_durable": true
   }

**Kafka**:

.. code-block:: json

   "messaging": {
     "broker_type": "kafka",
     "url": "kafka://localhost:9092",
     "topic_prefix": "payments.",
     "group_id": "payment-service",
     "auto_offset_reset": "earliest"
   }

**Redis**:

.. code-block:: json

   "messaging": {
     "broker_type": "redis",
     "url": "redis://localhost",
     "stream_maxlen": 1000,
     "consumer_group": "payment-service"
   }

**NATS**:

.. code-block:: json

   "messaging": {
     "broker_type": "nats",
     "url": "nats://localhost:4222",
     "subject_prefix": "payments.",
     "queue_group": "payment-service"
   }

**Memory** (For testing only):

.. code-block:: json

   "messaging": {
     "broker_type": "memory",
     "url": "memory://",
     "exchange_name": "payments"
   }

Environment variables can also be used:

.. code-block:: bash

   # RabbitMQ
   export PAYMENT_MESSAGING__BROKER_TYPE=rabbitmq
   export PAYMENT_MESSAGING__URL=amqp://guest:guest@localhost/
   
   # Kafka
   export PAYMENT_MESSAGING__BROKER_TYPE=kafka
   export PAYMENT_MESSAGING__URL=kafka://localhost:9092
   
   # Redis
   export PAYMENT_MESSAGING__BROKER_TYPE=redis
   export PAYMENT_MESSAGING__URL=redis://localhost