import json
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from fastapi_payments.providers.stripe import StripeProvider
from fastapi_payments.config.config_schema import ProviderConfig

from tests.fakes.fake_stripe import FakeStripe


@pytest.fixture
def stripe_provider():
    config = ProviderConfig(
        api_key="sk_test_mock_key",
        webhook_secret="whsec_mock_secret",
        sandbox_mode=True,
    )

    provider = StripeProvider(config)
    provider._run_stripe_calls_in_thread = False
    provider.stripe = FakeStripe()
    provider.stripe_error = provider.stripe.error
    return provider


@pytest.mark.asyncio
async def test_create_customer(stripe_provider):
    email = "test@example.com"
    name = "Test Customer"

    result = await stripe_provider.create_customer(email, name)

    assert result["email"] == email
    assert result["name"] == name
    assert "provider_customer_id" in result
    assert "created_at" in result


@pytest.mark.asyncio
async def test_create_customer_with_address(stripe_provider):
    email = "addr@example.com"
    name = "Address Test"
    address = {"line1": "123 Main St", "city": "Mumbai", "country": "IN", "postal_code": "400001"}

    result = await stripe_provider.create_customer(email, name, address=address)

    assert result["email"] == email
    assert result["name"] == name
    assert "provider_customer_id" in result


@pytest.mark.asyncio
async def test_retrieve_customer(stripe_provider):
    create_result = await stripe_provider.create_customer("test@example.com", "Test Customer")
    result = await stripe_provider.retrieve_customer(create_result["provider_customer_id"])

    assert "provider_customer_id" in result
    assert "email" in result
    assert "name" in result


@pytest.mark.asyncio
async def test_create_payment_method(stripe_provider):
    customer = await stripe_provider.create_customer("test@example.com", "Test Customer")
    payment_details = {"type": "card", "card": {"number": "4242424242424242", "exp_month": 12, "exp_year": 2030, "cvc": "123"}}

    result = await stripe_provider.create_payment_method(customer["provider_customer_id"], payment_details)

    assert "payment_method_id" in result
    assert result["type"] == "card"
    assert "card" in result


@pytest.mark.asyncio
async def test_attach_existing_payment_method(stripe_provider):
    customer = await stripe_provider.create_customer("test@example.com", "Test")
    pm = stripe_provider.stripe._payment_method_create(type="card", card={"number": "4242424242424242", "exp_month": 12, "exp_year": 2030, "cvc": "123"})

    result = await stripe_provider.create_payment_method(customer["provider_customer_id"], {"payment_method_id": pm["id"], "set_default": True})

    assert stripe_provider.stripe.payment_methods[pm["id"]]["customer"] == customer["provider_customer_id"]
    assert result["payment_method_id"] == pm["id"]


@pytest.mark.asyncio
async def test_create_payment_method_filters_unknown_keys(stripe_provider):
    customer = await stripe_provider.create_customer("f@example.com", "Filter Test")
    payment_details = {"type": "card", "card": {"number": "4242424242424242", "exp_month": 12, "exp_year": 2030, "cvc": "123"}, "unexpected_key": "should_be_filtered", "set_default": True}

    result = await stripe_provider.create_payment_method(customer["provider_customer_id"], payment_details)
    assert "payment_method_id" in result


@pytest.mark.asyncio
async def test_create_product(stripe_provider):
    result = await stripe_provider.create_product(name="Test Product", description="A test product")
    assert "provider_product_id" in result


@pytest.mark.asyncio
async def test_update_customer_accepts_address(stripe_provider):
    create_result = await stripe_provider.create_customer("u@example.com", "Update Test")
    provider_id = create_result["provider_customer_id"]
    update_payload = {"address": {"line1": "500 New Ln", "city": "Delhi", "country": "IN"}}
    result = await stripe_provider.update_customer(provider_id, update_payload)

    assert isinstance(result, dict)
    assert "updated_at" in result
    assert result["name"] == "Update Test"
    assert result.get("email") == "u@example.com"
    assert result.get("provider_customer_id") == provider_id


@pytest.mark.asyncio
async def test_create_price(stripe_provider):
    product = await stripe_provider.create_product("Test Product")
    result = await stripe_provider.create_price(product_id=product["provider_product_id"], amount=19.99, currency="USD", interval="month", interval_count=1)

    assert "provider_price_id" in result
    assert result["product_id"] == product["provider_product_id"]
    assert result["amount"] == 19.99
    assert result["currency"] == "USD"
    assert "recurring" in result
    assert result["recurring"]["interval"] == "month"


@pytest.mark.asyncio
async def test_create_subscription(stripe_provider):
    customer = await stripe_provider.create_customer("test@example.com", "Test Customer")
    product = await stripe_provider.create_product("Test Product")
    price = await stripe_provider.create_price(product_id=product["provider_product_id"], amount=19.99, currency="USD", interval="month")

    result = await stripe_provider.create_subscription(provider_customer_id=customer["provider_customer_id"], price_id=price["provider_price_id"], quantity=2)

    assert "provider_subscription_id" in result
    assert result["customer_id"] == customer["provider_customer_id"]
    assert result["price_id"] == price["provider_price_id"]
    assert result["quantity"] == 2
    assert result["status"] == "active"


@pytest.mark.asyncio
async def test_process_payment(stripe_provider):
    customer = await stripe_provider.create_customer("test@example.com", "Test Customer")
    payment_details = {"type": "card", "card": {"number": "4242424242424242", "exp_month": 12, "exp_year": 2030, "cvc": "123"}}

    payment_method = await stripe_provider.create_payment_method(customer["provider_customer_id"], payment_details)

    result = await stripe_provider.process_payment(amount=100.00, currency="USD", provider_customer_id=customer["provider_customer_id"], description="Test payment", payment_method_id=payment_method["payment_method_id"])

    assert "provider_payment_id" in result
    assert result["amount"] == 100.00
    assert result["currency"] == "USD"
    assert result["status"] == "succeeded"
    assert result["description"] == "Test payment"


@pytest.mark.asyncio
async def test_webhook_handler(stripe_provider):
    event_data = {"id": "evt_test", "type": "payment_intent.succeeded", "data": {"object": {"id": "pi_test", "amount": 1000, "currency": "usd", "customer": "cus_test"}}}

    result = await stripe_provider.webhook_handler(payload=event_data)

    assert result["event_type"] == "payment_intent.succeeded"
    assert result["standardized_event_type"] == "payment.succeeded"
    assert result["provider"] == "stripe"


@pytest.mark.asyncio
async def test_process_payment_declined_card(stripe_provider):
    customer = await stripe_provider.create_customer("declined@example.com", "Declined Customer")

    pm = await stripe_provider.create_payment_method(customer["provider_customer_id"], {"card": {"number": "4000000000000002", "exp_month": 12, "exp_year": 2030, "cvc": "123"}})

    with pytest.raises(Exception):
        await stripe_provider.process_payment(amount=50.00, currency="USD", provider_customer_id=customer["provider_customer_id"], payment_method_id=pm["payment_method_id"], description="Should be declined")


@pytest.mark.asyncio
async def test_process_payment_requires_3ds(stripe_provider):
    customer = await stripe_provider.create_customer("3ds@example.com", "3DS Customer")

    pm = await stripe_provider.create_payment_method(customer["provider_customer_id"], {"card": {"number": "4000000000003220", "exp_month": 12, "exp_year": 2030, "cvc": "123"}})

    result = await stripe_provider.process_payment(amount=75.00, currency="USD", provider_customer_id=customer["provider_customer_id"], payment_method_id=pm["payment_method_id"], description="Requires 3DS")

    assert result["status"] in ("requires_action", "requires_source_action", "requires_payment_method")
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from fastapi_payments.providers.stripe import StripeProvider
from fastapi_payments.config.config_schema import ProviderConfig

# Re-use shared FakeStripe helper so multiple tests can import it.
from tests.fakes.fake_stripe import FakeStripe


@pytest.fixture
def stripe_provider():
    """Create a test Stripe provider."""
    config = ProviderConfig(
        api_key="sk_test_mock_key",
        webhook_secret="whsec_mock_secret",
        sandbox_mode=True,
    )

    provider = StripeProvider(config)
    provider._run_stripe_calls_in_thread = False
    provider.stripe = FakeStripe()
    provider.stripe_error = provider.stripe.error

    return provider


@pytest.mark.asyncio
async def test_create_customer(stripe_provider):
    """Test creating a customer in Stripe."""
    email = "test@example.com"
    name = "Test Customer"

    result = await stripe_provider.create_customer(email, name)

    assert result["email"] == email
    assert result["name"] == name
    assert "provider_customer_id" in result
    assert "created_at" in result


@pytest.mark.asyncio
async def test_create_customer_with_address(stripe_provider):
    """Ensure create_customer accepts an optional address payload without error."""
    email = "addr@example.com"
    name = "Address Test"
    address = {"line1": "123 Main St", "city": "Mumbai", "country": "IN", "postal_code": "400001"}

    result = await stripe_provider.create_customer(email, name, address=address)

    assert result["email"] == email
    assert result["name"] == name
    assert "provider_customer_id" in result


@pytest.mark.asyncio
async def test_retrieve_customer(stripe_provider):
    """Test retrieving a customer from Stripe."""
    create_result = await stripe_provider.create_customer(
        "test@example.com", "Test Customer"
    )

    result = await stripe_provider.retrieve_customer(create_result["provider_customer_id"])

    assert "provider_customer_id" in result
    assert "email" in result
    assert "name" in result


@pytest.mark.asyncio
async def test_create_payment_method(stripe_provider):
    """Test creating a payment method in Stripe."""
    customer = await stripe_provider.create_customer(
        "test@example.com", "Test Customer"
    )

    payment_details = {
        "type": "card",
        "card": {
            "number": "4242424242424242",
            "exp_month": 12,
            "exp_year": 2030,
            "cvc": "123",
        },
    }

    result = await stripe_provider.create_payment_method(
        customer["provider_customer_id"], payment_details
    )

    assert "payment_method_id" in result
    assert result["type"] == "card"
    assert "card" in result


@pytest.mark.asyncio
async def test_attach_existing_payment_method(stripe_provider):
    """When a payment_method_id is provided we should attach it to the customer."""
    customer = await stripe_provider.create_customer("test@example.com", "Test")
    pm = stripe_provider.stripe._payment_method_create(
        type="card",
        card={"number": "4242424242424242", "exp_month": 12, "exp_year": 2030, "cvc": "123"},
    )

    result = await stripe_provider.create_payment_method(
        customer["provider_customer_id"], {"payment_method_id": pm["id"], "set_default": True}
    )

    assert stripe_provider.stripe.payment_methods[pm["id"]]["customer"] == customer["provider_customer_id"]
    assert result["payment_method_id"] == pm["id"]


@pytest.mark.asyncio
async def test_create_payment_method_filters_unknown_keys(stripe_provider):
    """Ensure unknown keys are not forwarded to PaymentMethod.create."""
    customer = await stripe_provider.create_customer("f@example.com", "Filter Test")

    payment_details = {
        "type": "card",
        "card": {"number": "4242424242424242", "exp_month": 12, "exp_year": 2030, "cvc": "123"},
        "unexpected_key": "should_be_filtered",
        "set_default": True,
    }

    result = await stripe_provider.create_payment_method(customer["provider_customer_id"], payment_details)
    assert "payment_method_id" in result


@pytest.mark.asyncio
async def test_create_product(stripe_provider):
    """Test creating a product in Stripe."""
    result = await stripe_provider.create_product(name="Test Product", description="A test product")

    assert "provider_product_id" in result


@pytest.mark.asyncio
async def test_update_customer_accepts_address(stripe_provider):
    """Ensure update_customer accepts an address payload and doesn't raise."""
    create_result = await stripe_provider.create_customer("u@example.com", "Update Test")
    provider_id = create_result["provider_customer_id"]

    update_payload = {"address": {"line1": "500 New Ln", "city": "Delhi", "country": "IN"}}
    result = await stripe_provider.update_customer(provider_id, update_payload)

    assert isinstance(result, dict)
    assert "updated_at" in result
    assert result["name"] == "Update Test"
    assert result.get("email") == "u@example.com"
    assert result.get("provider_customer_id") == provider_id


@pytest.mark.asyncio
async def test_create_price(stripe_provider):
    """Test creating a price in Stripe."""
    product = await stripe_provider.create_product("Test Product")

    result = await stripe_provider.create_price(
        product_id=product["provider_product_id"], amount=19.99, currency="USD", interval="month", interval_count=1
    )

    assert "provider_price_id" in result
    assert result["product_id"] == product["provider_product_id"]
    assert result["amount"] == 19.99
    assert result["currency"] == "USD"
    assert "recurring" in result
    assert result["recurring"]["interval"] == "month"


@pytest.mark.asyncio
async def test_create_subscription(stripe_provider):
    """Test creating a subscription in Stripe."""
    customer = await stripe_provider.create_customer("test@example.com", "Test Customer")
    product = await stripe_provider.create_product("Test Product")
    price = await stripe_provider.create_price(product_id=product["provider_product_id"], amount=19.99, currency="USD", interval="month")

    result = await stripe_provider.create_subscription(
        provider_customer_id=customer["provider_customer_id"], price_id=price["provider_price_id"], quantity=2
    )

    assert "provider_subscription_id" in result
    assert result["customer_id"] == customer["provider_customer_id"]
    assert result["price_id"] == price["provider_price_id"]
    assert result["quantity"] == 2
    assert result["status"] == "active"


@pytest.mark.asyncio
async def test_process_payment(stripe_provider):
    """Test processing a payment with Stripe."""
    customer = await stripe_provider.create_customer("test@example.com", "Test Customer")

    payment_details = {"type": "card", "card": {"number": "4242424242424242", "exp_month": 12, "exp_year": 2030, "cvc": "123"}}

    payment_method = await stripe_provider.create_payment_method(customer["provider_customer_id"], payment_details)

    result = await stripe_provider.process_payment(
        amount=100.00,
        currency="USD",
        provider_customer_id=customer["provider_customer_id"],
        description="Test payment",
        payment_method_id=payment_method["payment_method_id"],
    )

    assert "provider_payment_id" in result
    assert result["amount"] == 100.00
    assert result["currency"] == "USD"
    assert result["status"] == "succeeded"
    assert result["description"] == "Test payment"


@pytest.mark.asyncio
async def test_webhook_handler(stripe_provider):
    """Test handling a webhook from Stripe."""
    event_data = {"id": "evt_test", "type": "payment_intent.succeeded", "data": {"object": {"id": "pi_test", "amount": 1000, "currency": "usd", "customer": "cus_test"}}}

    result = await stripe_provider.webhook_handler(payload=event_data)

    assert result["event_type"] == "payment_intent.succeeded"
    assert result["standardized_event_type"] == "payment.succeeded"
    assert result["provider"] == "stripe"


@pytest.mark.asyncio
async def test_process_payment_declined_card(stripe_provider):
    """Simulate a declined card using Stripe's test card 4000 0000 0000 0002."""
    customer = await stripe_provider.create_customer("declined@example.com", "Declined Customer")

    pm = await stripe_provider.create_payment_method(
        customer["provider_customer_id"], {"card": {"number": "4000000000000002", "exp_month": 12, "exp_year": 2030, "cvc": "123"}}
    )

    with pytest.raises(Exception):
        await stripe_provider.process_payment(
            amount=50.00,
            currency="USD",
            provider_customer_id=customer["provider_customer_id"],
            payment_method_id=pm["payment_method_id"],
            description="Should be declined",
        )


@pytest.mark.asyncio
async def test_process_payment_requires_3ds(stripe_provider):
    """Simulate a 3D Secure required payment using Stripe's test card 4000 0000 0000 3220."""
    customer = await stripe_provider.create_customer("3ds@example.com", "3DS Customer")

    pm = await stripe_provider.create_payment_method(
        customer["provider_customer_id"], {"card": {"number": "4000000000003220", "exp_month": 12, "exp_year": 2030, "cvc": "123"}}
    )

    result = await stripe_provider.process_payment(
        amount=75.00,
        currency="USD",
        provider_customer_id=customer["provider_customer_id"],
        payment_method_id=pm["payment_method_id"],
        description="Requires 3DS",
    )



@pytest.mark.asyncio
async def test_create_price(stripe_provider):
    """Test creating a price in Stripe."""
    # Create a product first
    product = await stripe_provider.create_product("Test Product")

    result = await stripe_provider.create_price(
        product_id=product["provider_product_id"],
        amount=19.99,
        currency="USD",
        interval="month",
        interval_count=1,
    )

    assert "provider_price_id" in result
    assert result["product_id"] == product["provider_product_id"]
    assert result["amount"] == 19.99
    assert result["currency"] == "USD"
    assert "recurring" in result
    assert result["recurring"]["interval"] == "month"


@pytest.mark.asyncio
async def test_create_subscription(stripe_provider):
    """Test creating a subscription in Stripe."""
    # Create a customer first
    customer = await stripe_provider.create_customer(
        "test@example.com", "Test Customer"
    )

    # Create a product
    product = await stripe_provider.create_product("Test Product")

    # Create a price
    price = await stripe_provider.create_price(
        product_id=product["provider_product_id"],
        amount=19.99,
        currency="USD",
        interval="month",
    )

    result = await stripe_provider.create_subscription(
        provider_customer_id=customer["provider_customer_id"],
        price_id=price["provider_price_id"],
        quantity=2,
    )

    assert "provider_subscription_id" in result
    assert result["customer_id"] == customer["provider_customer_id"]
    assert result["price_id"] == price["provider_price_id"]
    assert result["quantity"] == 2
    assert result["status"] == "active"


@pytest.mark.asyncio
async def test_process_payment(stripe_provider):
    """Test processing a payment with Stripe."""
    # Create a customer first
    customer = await stripe_provider.create_customer(
        "test@example.com", "Test Customer"
    )

    payment_details = {
        "type": "card",
        "card": {
            "number": "4242424242424242",
            "exp_month": 12,
            "exp_year": 2030,
            "cvc": "123",
        },
    }

    payment_method = await stripe_provider.create_payment_method(
        customer["provider_customer_id"], payment_details
    )

    result = await stripe_provider.process_payment(
        amount=100.00,
        currency="USD",
        provider_customer_id=customer["provider_customer_id"],
        description="Test payment",
        payment_method_id=payment_method["payment_method_id"],
    )

    assert "provider_payment_id" in result
    assert result["amount"] == 100.00
    assert result["currency"] == "USD"
    assert result["status"] == "succeeded"
    assert result["description"] == "Test payment"


@pytest.mark.asyncio
async def test_webhook_handler(stripe_provider):
    """Test handling a webhook from Stripe."""
    # Test a payment succeeded event
    event_data = {
        "id": "evt_test",
        "type": "payment_intent.succeeded",
        "data": {
            "object": {
                "id": "pi_test",
                "amount": 1000,
                "currency": "usd",
                "customer": "cus_test",
            }
        },
    }

    result = await stripe_provider.webhook_handler(payload=event_data)

    assert result["event_type"] == "payment_intent.succeeded"
    assert result["standardized_event_type"] == "payment.succeeded"
    assert result["provider"] == "stripe"


@pytest.mark.asyncio
async def test_process_payment_declined_card(stripe_provider):
    """Simulate a declined card using Stripe's test card 4000 0000 0000 0002."""
    customer = await stripe_provider.create_customer(
        "declined@example.com", "Declined Customer"
    )

    # Create a payment method that simulates a generic decline
    pm = await stripe_provider.create_payment_method(
        customer["provider_customer_id"],
        {"card": {"number": "4000000000000002", "exp_month": 12, "exp_year": 2030, "cvc": "123"}},
    )

    with pytest.raises(Exception):
        await stripe_provider.process_payment(
            amount=50.00,
            currency="USD",
            provider_customer_id=customer["provider_customer_id"],
            payment_method_id=pm["payment_method_id"],
            description="Should be declined",
        )


@pytest.mark.asyncio
async def test_process_payment_requires_3ds(stripe_provider):
    """Simulate a 3D Secure required payment using Stripe's test card 4000 0000 0000 3220."""
    customer = await stripe_provider.create_customer(
        "3ds@example.com", "3DS Customer"
    )

    pm = await stripe_provider.create_payment_method(
        customer["provider_customer_id"],
        {"card": {"number": "4000000000003220", "exp_month": 12, "exp_year": 2030, "cvc": "123"}},
    )

    result = await stripe_provider.process_payment(
        amount=75.00,
        currency="USD",
        provider_customer_id=customer["provider_customer_id"],
        payment_method_id=pm["payment_method_id"],
        description="Requires 3DS",
    )

    assert result["status"] in ("requires_action", "requires_source_action", "requires_payment_method")
