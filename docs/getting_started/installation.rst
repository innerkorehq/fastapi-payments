Installation
===========

Basic Installation
----------------

Install FastAPI Payments using pip:

.. code-block:: bash

   pip install fastapi-payments

Optional Dependencies
-------------------

FastAPI Payments offers optional dependencies for different payment providers:

.. code-block:: bash

   # Install with Stripe support
   pip install "fastapi-payments[stripe]"
   
   # Install with PayPal support
   pip install "fastapi-payments[paypal]"
   
   # Install with Adyen support
   pip install "fastapi-payments[adyen]"
   
   # Install all providers
   pip install "fastapi-payments[all]"
   
   # Install development dependencies
   pip install "fastapi-payments[dev]"

Requirements
-----------

FastAPI Payments requires:

* Python 3.8 or higher
* FastAPI 0.95.0 or higher
* SQLAlchemy 2.0.0 or higher
* FastStream 0.2.0 or higher

For database connectivity, you'll need the appropriate database driver:

.. code-block:: bash

   # PostgreSQL
   pip install asyncpg
   
   # MySQL
   pip install aiomysql
   
   # SQLite
   pip install aiosqlite