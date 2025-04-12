FastAPI Payments Documentation
=============================

.. image:: _static/logo.png
   :alt: FastAPI Payments Logo
   :align: center
   :width: 300px

A flexible, extensible payment processing library for FastAPI applications.

**Key Features**:

* Multiple payment providers (Stripe, PayPal, Adyen)
* Flexible pricing models (subscription, usage-based, tiered, etc.)
* Asynchronous architecture with FastAPI and SQLAlchemy
* Event-driven design with RabbitMQ integration
* Highly configurable via JSON or environment variables
* Comprehensive testing support

.. code-block:: python

   from fastapi import FastAPI
   from fastapi_payments import FastAPIPayments
   import json
   
   # Create FastAPI app
   app = FastAPI()
   
   # Load configuration
   with open("payment_config.json") as f:
       config = json.load(f)
   
   # Initialize payments module
   payments = FastAPIPayments(config)
   
   # Include payment routes
   payments.include_router(app, prefix="/api")

Quick Links
----------

* :doc:`getting_started/installation`
* :doc:`getting_started/quickstart`
* :doc:`concepts/index`
* :doc:`examples/index`
* :doc:`api/index`

.. toctree::
   :maxdepth: 2
   :caption: Contents:
   :hidden:

   getting_started/index
   concepts/index
   examples/index
   advanced/index
   api/index
   contributing/index

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`