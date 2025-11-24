import pytest

from fastapi_payments.services.payment_service import PaymentService
from fastapi_payments.config.config_schema import PaymentConfig
from fastapi_payments.db.repositories import get_db, CustomerRepository, PaymentMethodRepository


@pytest.mark.asyncio
async def test_create_and_list_payment_method_persists(initialize_test_dependencies, mock_event_publisher):
    """Creating a payment method should persist it server-side and become listable."""
    cfg = initialize_test_dependencies

    service = PaymentService(cfg, mock_event_publisher, None)

    # Acquire a db session from the app's repository fixture
    async for session in get_db():
        # attach session to service
        service.set_db_session(session)

        # Create a test customer directly in DB (avoid provider calls)
        customer_repo = CustomerRepository(session)
        customer = await customer_repo.create(email="persist@example.com", name="Persist User")

        # Inject a simple centralized fake provider
        from tests.fakes.fake_providers import FakePaymentMethodProvider

        # Put the fake provider into the service
        service.providers["stripe"] = FakePaymentMethodProvider()

        # Add a provider_customer link so service can find provider customer
        await customer_repo.add_provider_customer(customer.id, "stripe", "prov_cust_1")

        # Call create_payment_method — should persist via PaymentMethodRepository
        result = await service.create_payment_method(customer.id, {"type": "card"}, provider="stripe")

        assert result["id"] in ("pm_test_123",) or result.get("stored_id")
        assert result["provider"] == "stripe"

        # Verify repository record exists
        pm_repo = PaymentMethodRepository(session)
        stored = await pm_repo.get_by_provider_method_id("stripe", "pm_test_123")
        assert stored is not None
        assert stored.mandate_id == "mandate_test_abc"

        # Now list via service — should return the stored method
        methods = await service.list_payment_methods(customer.id, provider="stripe")
        assert any(m["id"] == "pm_test_123" for m in methods)

        break
