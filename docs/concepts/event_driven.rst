Event-Driven Architecture
=======================

Overview
-------

FastAPI Payments uses an event-driven architecture with support for multiple message brokers to handle asynchronous operations and integrations with external systems.

Supported Message Brokers
-----------------------

1. **RabbitMQ**
   - Default message broker
   - Topic-based routing with exchanges
   - Durable queues for reliability
   - Supports complex routing patterns

2. **Kafka**
   - High throughput message broker
   - Excellent for high-volume systems
   - Long-term message retention
   - Horizontal scalability

3. **Redis**
   - Lightweight message broker using Redis Streams
   - Great for simpler use cases
   - Low latency
   - Useful when Redis is already part of your stack

4. **NATS**
   - Ultra fast messaging system
   - Supports request-reply pattern
   - Simple and lightweight
   - Lower footprint than RabbitMQ or Kafka

5. **Memory**
   - In-memory broker for testing
   - No external dependencies
   - Not for production use

Broker Configuration
------------------

Configure your preferred message broker in your configuration:

RabbitMQ (Default)
^^^^^^^^^^^^^^^^^

.. code-block:: json

   {
     "messaging": {
       "broker_type": "rabbitmq",
       "url": "amqp://guest:guest@localhost/",
       "exchange_name": "payments",
       "queue_prefix": "payment_",
       "exchange_type": "topic",
       "exchange_durable": true
     }
   }

Kafka
^^^^^

.. code-block:: json

   {
     "messaging": {
       "broker_type": "kafka",
       "url": "kafka://localhost:9092",
       "topic_prefix": "payments.",
       "group_id": "payment-service",
       "auto_offset_reset": "earliest"
     }
   }

Redis
^^^^

.. code-block:: json

   {
     "messaging": {
       "broker_type": "redis",
       "url": "redis://localhost",
       "stream_maxlen": 1000,
       "consumer_group": "payment-service"
     }
   }

NATS
^^^^

.. code-block:: json

   {
     "messaging": {
       "broker_type": "nats",
       "url": "nats://localhost:4222",
       "subject_prefix": "payments.",
       "queue_group": "payment-service"
     }
   }

Event Types
---------

The library publishes events for various payment activities:

Customer Events
^^^^^^^^^^^^^

- ``payment.customer.created``: Customer created
- ``payment.customer.updated``: Customer updated
- ``payment.customer.deleted``: Customer deleted

Payment Method Events
^^^^^^^^^^^^^^^^^

- ``payment.method.created``: Payment method added
- ``payment.method.updated``: Payment method updated
- ``payment.method.deleted``: Payment method removed

Subscription Events
^^^^^^^^^^^^^^^

- ``payment.subscription.created``: Subscription created
- ``payment.subscription.updated``: Subscription updated
- ``payment.subscription.canceled``: Subscription canceled
- ``payment.subscription.renewed``: Subscription renewed

Payment Events
^^^^^^^^^^^

- ``payment.transaction.created``: Payment initiated
- ``payment.transaction.succeeded``: Payment completed successfully
- ``payment.transaction.failed``: Payment failed
- ``payment.transaction.refunded``: Payment refunded

Invoice Events
^^^^^^^^^^^

- ``payment.invoice.created``: Invoice created
- ``payment.invoice.updated``: Invoice updated
- ``payment.invoice.paid``: Invoice paid
- ``payment.invoice.payment_failed``: Invoice payment failed

Usage Events
^^^^^^^^^^

- ``payment.usage.recorded``: Usage recorded for usage-based billing

Publishing Events
--------------

The library automatically publishes events during payment operations. You can also publish custom events:

.. code-block:: python

   from fastapi_payments.messaging.publishers import PaymentEventPublisher
   
   # Publisher instance is available from PaymentService
   await payment_service.event_publisher.publish_event(
       event_type="payment.custom.event",
       data={
           "custom_id": "123",
           "details": "Custom event details"
       }
   )

Consuming Events
-------------

Register handlers for payment events:

.. code-block:: python

   from fastapi_payments.messaging.consumers import PaymentEventConsumer
   from fastapi_payments.config.settings import load_config
   
   # Load configuration
   config = load_config("payment_config.json")
   
   # Create consumer
   consumer = PaymentEventConsumer(config.messaging)
   
   # Define handler
   async def handle_payment_succeeded(message):
       payment_id = message["data"]["payment_id"]
       amount = message["data"]["amount"]
       print(f"Payment {payment_id} for {amount} succeeded")
   
   # Register handler
   await consumer.register_handler(
       "payment.transaction.succeeded", 
       handle_payment_succeeded
   )
   
   # Start consuming
   await consumer.start()

Using Default Handlers
-------------------

The library provides default handlers for common events:

.. code-block:: python

   from fastapi_payments.messaging.consumers import setup_default_consumers
   
   # Create consumer
   consumer = PaymentEventConsumer(config.messaging)
   
   # Register default handlers
   await setup_default_consumers(consumer)
   
   # Start consuming events
   await consumer.start()

Best Practices
-----------

1. **Make event handlers idempotent**: Events may be delivered more than once
2. **Use descriptive routing keys**: Makes it easier to filter and process events
3. **Keep event payloads small**: Include IDs and essential data, not entire objects
4. **Choose the right broker**: Match your broker choice to your scaling needs
5. **Implement dead-letter handling**: Capture failed message processing
6. **Monitor broker health**: Prevent message buildup or processing delays