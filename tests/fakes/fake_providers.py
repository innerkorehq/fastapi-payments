class FakePaymentMethodProvider:
    """Simple fake provider used by service-level tests that need a
    provider that returns a provider-level payment method id and optional
    mandate info.
    """

    async def create_payment_method(self, provider_customer_id, payment_details):
        # Keep implementation minimal and deterministic for tests
        return {
            "payment_method_id": "pm_test_123",
            "type": "card",
            "card": {"brand": "visa", "last4": "4242", "exp_month": 12, "exp_year": 2030},
            "is_default": True,
            # Pretend SetupIntent created a mandate
            "mandate_id": "mandate_test_abc",
        }
