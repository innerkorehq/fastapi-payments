import pytest

from fastapi_payments.services.payment_service import PaymentService
from fastapi_payments.db.repositories import get_db, CustomerRepository, PaymentMethodRepository


@pytest.mark.asyncio
async def test_set_default_and_delete_methods(initialize_test_dependencies, mock_event_publisher):
    service: PaymentService = PaymentService(initialize_test_dependencies, mock_event_publisher, None)

    # Create a DB session
    async for session in get_db():
        service.set_db_session(session)

        # Create a customer and provider link
        customer_repo = CustomerRepository(session)
        customer = await customer_repo.create(email="user@test.com", name="User Test")
        await customer_repo.add_provider_customer(customer.id, "stripe", "prov_123")

        pm_repo = PaymentMethodRepository(session)

        # Create two stored payment methods
        pm1 = await pm_repo.create(
            customer_id=customer.id,
            provider="stripe",
            provider_payment_method_id="pm_a",
            is_default=False,
            card_brand="visa",
            card_last4="1111",
        )

        pm2 = await pm_repo.create(
            customer_id=customer.id,
            provider="stripe",
            provider_payment_method_id="pm_b",
            is_default=False,
            card_brand="visa",
            card_last4="2222",
        )

        # Set pm2 as default
        res = await service.set_default_payment_method(customer.id, pm2.id)
        assert res["is_default"] is True

        # Ensure pm2 is default in DB and pm1 is not
        stored1 = await pm_repo.get_by_id(pm1.id)
        stored2 = await pm_repo.get_by_id(pm2.id)
        assert not stored1.is_default
        assert stored2.is_default

        # Delete pm1
        deleted = await service.delete_payment_method(customer.id, pm1.id)
        assert deleted["deleted"]

        # pm1 should no longer exist
        assert (await pm_repo.get_by_id(pm1.id)) is None

        break
