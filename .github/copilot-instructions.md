## FastAPI Payments — Copilot instructions (concise)

High-level context
- Code lives under `src/fastapi_payments` and exports the library via `FastAPIPayments` (see `__init__.py`) — this is both a library and an example HTTP API module for FastAPI apps.
- Key responsibilities: provider integrations (Stripe, PayPal, Adyen, PayU), REST API, async SQLAlchemy persistence (repositories), service orchestration, and event messaging.

Where to look first (important files)
- API: `src/fastapi_payments/api/routes.py` (API endpoints, background sync endpoints)
- Business logic: `src/fastapi_payments/services/payment_service.py` (provider ↔ DB orchestration)
- Provider pattern: `src/fastapi_payments/providers/base.py` (abstract class) and `providers/stripe.py` (example implementation)
- DB: `src/fastapi_payments/db/models.py` + repositories in `src/fastapi_payments/db/repositories/`
- Schemas: `src/fastapi_payments/schemas/payment.py` — canonical Pydantic models

Testing & local dev
- Tests use `pytest` + `pytest-asyncio` and a test sqlite DB at `tests/test_payments.db` (created during tests).
- Unit tests use an in-memory `FakeStripe` located in `tests/fakes/fake_stripe.py`. `tests/conftest.py` injects this fake into the global test PaymentService so tests don't call real Stripe.

Stripe testing notes
- Follow Stripe testing docs: https://docs.stripe.com/testing and https://docs.stripe.com/billing/testing for billing-specific flows.
- Prefer server-side test `PaymentMethod` ids (eg. `pm_card_visa`) when writing integration tests. For UI/form tests, interactive card numbers like `4242 4242 4242 4242` are fine.
- Common cards to use in tests:
	- Successful Visa: 4242 4242 4242 4242 or `pm_card_visa`
	- Generic decline: 4000 0000 0000 0002 (triggers card_declined)
	- 3D Secure required: 4000 0000 0000 3220 (requires action / SCA)
	- Decline after attach (useful for subscription test): 4000 0000 0000 0341
	- Insufficient funds: 4000 0000 0000 9995
- Our test FakeStripe (tests/fakes/fake_stripe.py) simulates some of these cases (declines & 3DS) — add more simulation cases there if you need to exercise other Stripe test cards.

Common conventions to follow
- Provider IDs are named consistently (provider_customer_id, provider_product_id, provider_price_id, provider_payment_id).
- Repositories accept an AsyncSession and return either a SQLAlchemy model instance or normalized dicts; always use the repository APIs rather than interacting with the models directly in service code.
- PaymentService is the single place for coordinating provider actions and DB persistence. Aim to keep business logic there rather than in routes.

Dev commands (common tasks)
- Run full tests: `pytest -q`
- Run a single test: `pytest tests/test_providers/test_stripe.py::test_create_customer -q`
- Run the example app: `uvicorn app:app --reload` (or use an example main which calls `FastAPIPayments` and includes the router).

Practical tips for contributors / AI agents
- When adding a provider method, implement it on `PaymentProvider` (base) and mirror formatting helpers found in `providers/stripe.py` (e.g., `_format_*` helpers).
- For DB schema changes add matching Alembic migration before release; update repositories + unit tests accordingly.
- Sync and background jobs: small experiments use FastAPI `BackgroundTasks` + `SyncJob` DB records, but production should use an external worker (Celery/RQ). Ensure background work creates its own AsyncSession.
- Tests must be hermetic — prefer the `FakeStripe` or explicit mocking to avoid network calls and flaky tests.

If anything is missing or you'd like targeted instructions for a different area (e.g., how providers map to DB rows, or how to extend background jobs), tell me and I’ll expand.
