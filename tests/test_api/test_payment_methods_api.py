import pytest
from httpx import AsyncClient, ASGITransport

from fastapi_payments.db.repositories import get_db, CustomerRepository, PaymentMethodRepository


@pytest.mark.asyncio
async def test_api_set_default_and_delete(test_app, initialize_test_dependencies):
    # Insert a customer and saved payment method directly into DB
    async for session in get_db():
        cust_repo = CustomerRepository(session)
        customer = await cust_repo.create(email="apiuser@test.com", name="API User")
        await cust_repo.add_provider_customer(customer.id, "stripe", "prov_1")

        pm_repo = PaymentMethodRepository(session)
        pm = await pm_repo.create(
            customer_id=customer.id,
            provider="stripe",
            provider_payment_method_id="pm_api_1",
            is_default=False,
            card_brand="visa",
            card_last4="0001",
        )

        break

    # Mark as default via API
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        resp = await client.post(f"/payments/customers/{customer.id}/payment-methods/{pm.id}/default")
        assert resp.status_code == 200
        body = resp.json()
        assert body.get("is_default") is True

        # Delete via API
        del_resp = await client.delete(f"/payments/customers/{customer.id}/payment-methods/{pm.id}")
        assert del_resp.status_code == 200
        assert del_resp.json().get("deleted") is True
