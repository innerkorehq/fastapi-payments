import asyncio
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from fastapi_payments import FastAPIPayments
from fastapi_payments.config.config_schema import DatabaseConfig
from fastapi_payments.db.repositories import initialize_db
from fastapi_payments.api.dependencies import initialize_dependencies
from fastapi_payments.config.config_schema import PaymentConfig

CONFIG = {
    "providers": {
        "stripe": {"api_key": "sk_test_mock_key", "webhook_secret": "whsec_mock_secret", "sandbox_mode": True}
    },
    "database": {"url": "sqlite+aiosqlite:///./test_subscriptions.db", "echo": False},
    "messaging": {"broker_type": "memory", "url": "memory://", "exchange_name": "test_exchange", "queue_prefix": "test_"},
    "default_provider": "stripe",
}

async def run():
    # Initialize module-level dependencies (providers, publishers, etc.)
    initialize_dependencies(PaymentConfig(**CONFIG))

    db_cfg = DatabaseConfig(**CONFIG["database"])
    initialize_db(db_cfg)
    app = FastAPI()
    payments = FastAPIPayments(CONFIG)
    payments.include_router(app)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post('/payments/customers', json={"email": "sub@ex.com", "name": "Sub User"})
        print('create customer status', resp.status_code, 'body', resp.text)
        cust = resp.json()
        cid = cust.get('id')
        print('customer id', cid)

        resp2 = await client.get(f'/payments/customers/{cid}/subscriptions')
        print('list subs status', resp2.status_code)
        print('list subs body', resp2.text)

if __name__ == '__main__':
    asyncio.run(run())
