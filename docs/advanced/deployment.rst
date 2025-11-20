Deployment Guide
================

This guide outlines a repeatable process for promoting FastAPI Payments from
local development to production. It assumes you manage a FastAPI application
and want the payments stack to run inside the same cluster or service mesh.

Prerequisites
-------------

* Python 3.10+ runtime (CPython recommended)
* PostgreSQL 13+ or compatible database for the SQLAlchemy models
* Message broker (Redis, RabbitMQ, Kafka, NATS, etc.) if you emit events
* Access to provider credentials (Stripe, PayPal, Adyen, PayU, ...)
* Container runtime (Docker/Podman) or process manager (systemd, supervisord)

Build Artifacts
---------------

1. Install dependencies:

   .. code-block:: bash

      python -m venv .venv
      source .venv/bin/activate
      pip install -U pip
      pip install -e .[dev]

2. Compile static assets (optional, only if you vend docs or stub UIs):

   .. code-block:: bash

      npm install && npm run build  # only required for demos

3. Run tests and type checks:

   .. code-block:: bash

      pytest
      mypy src/fastapi_payments

4. Package the application (optional):

   .. code-block:: bash

      python -m build
      # wheel lives in dist/

Runtime Configuration
---------------------

FastAPI Payments loads settings via :mod:`fastapi_payments.config.settings`.
Choose a configuration source that matches your environment:

================= =============================================================
Source            Description
================= =============================================================
``payment_config.json``  Full JSON document (used in examples and tutorial).
Environment variables    Override specific keys, ideal for container secrets.
Pydantic settings        Instantiate :class:`~fastapi_payments.config.config_schema.PaymentConfig`
                         directly inside your FastAPI startup.
================= =============================================================

Set the following variables before starting the API server:

* ``DATABASE__URL`` – Async SQLAlchemy connection string
* ``PAYMENTS__PROVIDERS__stripe__api_key`` (same schema for each provider)
* ``RABBITMQ__URL`` (or ``MESSAGING__URL``) if you emit events
* ``PAYMENTS__DEFAULT_PROVIDER`` for the provider fallback

Example (using ``dotenv`` syntax)::

   DATABASE__URL=postgresql+asyncpg://app:pass@db/payments
   PAYMENTS__PROVIDERS__stripe__api_key=sk_live_***
   PAYMENTS__PROVIDERS__payu__api_key=merchantKey
   PAYMENTS__PROVIDERS__payu__api_secret=merchantSalt
   PAYMENTS__PROVIDERS__payu__additional_settings__success_url=https://api.example.com/payu/success

Database Migrations
-------------------

The ORM models live in :mod:`fastapi_payments.db.models`. Apply migrations
before deploying a new version. Alembic is the recommended tool:

.. code-block:: bash

   alembic upgrade head

If you prefer to bloat migrations outside this repo, import the metadata in
your host service and manage migrations there.

Application Startup
-------------------

1. Bind the FastAPI router:

   .. code-block:: python

      payments = FastAPIPayments(config)
      payments.include_router(app, prefix="/payments")

2. Start a background worker for the messaging callbacks (optional):

   .. code-block:: bash

      fastapi-payments-events --config payment_config.json

3. Serve the API:

   .. code-block:: bash

      uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

Kubernetes Tips
----------------

* Mount provider secrets as environment variables.
* Run ``uvicorn`` in a deployment with liveness/readiness checks on ``/health``.
* Keep migrations and workers in dedicated Jobs/Deployments so they scale
  independently.
* Attach a ``PodDisruptionBudget`` to avoid dropping webhook processing during
  node rotations.

Rollback Strategy
-----------------

* Keep at least one previous wheel/image in your registry.
* Downgrade database schema only if absolutely necessary; otherwise, prefer
  backward-compatible migrations.
* Disable new providers (e.g., PayU) via configuration before rolling back
  code to avoid mismatched hash logic.
