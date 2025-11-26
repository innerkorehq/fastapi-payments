import pytest

from fastapi_payments.config.config_schema import ProviderConfig
from fastapi_payments.providers.payu import PayUProvider


@pytest.fixture
def payu_provider():
    config = ProviderConfig(
        api_key="gtKFFx",
        api_secret="eCwWELxi",
        sandbox_mode=True,
        additional_settings={
            "success_url": "https://merchant.test/success",
            "failure_url": "https://merchant.test/failure",
        },
    )
    return PayUProvider(config)


@pytest.mark.asyncio
async def test_process_payment_includes_redirect_payload(payu_provider):
    result = await payu_provider.process_payment(
        amount=10.0,
        currency="INR",
        provider_customer_id="cust_123",
        meta_info={
            "payu": {
                "firstname": "John",
                "email": "john@example.com",
                "productinfo": "Subscription",
                "phone": "9999999999",
                "txnid": "123456789",
            },
            "customer_context": {
                "name": "John",
                "email": "john@example.com",
            },
        },
    )

    redirect_data = result["meta_info"]["redirect"]
    fields = redirect_data["fields"]

    assert redirect_data["action_url"].endswith("_payment")
    assert fields["key"] == payu_provider.merchant_key
    assert fields["hash"] == payu_provider._sign_request(fields)


@pytest.mark.asyncio
async def test_webhook_handler_validates_hash(payu_provider):
    payload = {
        "status": "success",
        "txnid": "Txn001",
        "amount": "10.00",
        "productinfo": "Order",
        "firstname": "John",
        "email": "john@example.com",
        "key": payu_provider.merchant_key,
    }
    payload["hash"] = payu_provider._sign_response(payload)

    result = await payu_provider.webhook_handler(payload)
    assert result["standardized_event_type"] == "payment.succeeded"


@pytest.mark.asyncio
async def test_process_payment_requires_contact_details(payu_provider):
    with pytest.raises(ValueError):
        await payu_provider.process_payment(
            amount=5.0,
            currency="INR",
            provider_customer_id="cust_456",
            meta_info={
                "payu": {"productinfo": "Test", "txnid": "abc"},
                "customer_context": {},
            },
        )


@pytest.mark.asyncio
async def test_process_payment_accepts_mandate_id(payu_provider):
    """Should accept a mandate_id kw without raising even though PayU ignores it."""
    result = await payu_provider.process_payment(
        amount=20.0,
        currency="INR",
        provider_customer_id="cust_mandate",
        meta_info={
            "payu": {"firstname": "Alice", "email": "alice@example.com", "productinfo": "Buy", "txnid": "tx_1"},
            "customer_context": {"name": "Alice", "email": "alice@example.com"},
        },
        mandate_id="mand_12345",
    )

    assert "meta_info" in result and "redirect" in result["meta_info"]
