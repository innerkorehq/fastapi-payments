Setup
=====

Database Setup
-------------

FastAPI Payments requires a database to store payment data. The library will automatically create the necessary database tables when initialized.

For production use, you should use Alembic for migrations:

.. code-block:: bash

   # Install alembic
   pip install alembic
   
   # Initialize alembic
   alembic init migrations
   
   # Create a migration
   alembic revision --autogenerate -m "Initial payment tables"
   
   # Run the migration
   alembic upgrade head

RabbitMQ Setup
------------

While not required for basic functionality, FastAPI Payments leverages RabbitMQ for event-driven operations. You can:

1. Install RabbitMQ locally:

   .. code-block:: bash
   
      # Debian/Ubuntu
      sudo apt-get install rabbitmq-server
      
      # macOS
      brew install rabbitmq
      
      # Start the service
      sudo service rabbitmq-server start

2. Use Docker:

   .. code-block:: bash
   
      docker run -d --name rabbitmq -p 5672:5672 -p 15672:15672 rabbitmq:3-management

3. Use a cloud service like CloudAMQP

   Configure the URL in your settings.

Provider Accounts
--------------

You'll need to create accounts with the payment providers you intend to use:

Stripe
^^^^^^

1. Create a Stripe account at https://stripe.com
2. Get your API keys from the Developer Dashboard
3. Configure webhooks for your environment

PayPal
^^^^^^

1. Create a PayPal Developer account at https://developer.paypal.com
2. Create an application to get your client ID and secret
3. Configure webhooks for your environment

Adyen
^^^^^

1. Create an Adyen account at https://www.adyen.com
2. Get your API key and merchant account
3. Configure webhooks for your environment