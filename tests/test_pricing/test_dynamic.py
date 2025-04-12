from fastapi_payments.pricing.dynamic import DynamicPricing


def test_dynamic_pricing_calculation():
    """Test dynamic pricing calculation with different multipliers."""
    # Basic price with default multiplier (1.0) and no tax
    pricing1 = DynamicPricing(
        base_price=10.0, default_multiplier=1.0, tax_rate=0.0)
    price1 = pricing1.calculate_price()
    assert price1 == 10.0  # 10.0 * 1.0, no tax

    # With tax
    pricing2 = DynamicPricing(
        base_price=10.0, default_multiplier=1.0, tax_rate=0.1)
    price2 = pricing2.calculate_price()
    assert price2 == 11.0  # 10.0 * 1.0 + 10% tax

    # With custom multiplier
    pricing3 = DynamicPricing(
        base_price=10.0, default_multiplier=1.0, tax_rate=0.1)
    price3 = pricing3.calculate_price(custom_multiplier=1.5)
    assert price3 == 16.5  # 10.0 * 1.5 + 10% tax

    # Override tax rate
    pricing4 = DynamicPricing(
        base_price=10.0, default_multiplier=1.0, tax_rate=0.1)
    price4 = pricing4.calculate_price(tax_rate=0.2)
    assert price4 == 12.0  # 10.0 * 1.0 + 20% tax

    # Combined custom multiplier and tax override
    pricing5 = DynamicPricing(
        base_price=10.0, default_multiplier=1.0, tax_rate=0.1)
    price5 = pricing5.calculate_price(custom_multiplier=2.0, tax_rate=0.05)
    assert price5 == 21.0  # 10.0 * 2.0 + 5% tax


def test_dynamic_pricing_billing_items():
    """Test billing items for dynamic pricing."""
    # No multiplier adjustment (default multiplier is used)
    pricing1 = DynamicPricing(base_price=10.0, default_multiplier=1.0)
    items1 = pricing1.get_billing_items()
    assert len(items1) == 1
    assert items1[0]["description"] == "Base price"
    assert items1[0]["amount"] == 10.0

    # With default multiplier > 1.0 (adds multiplier adjustment)
    pricing2 = DynamicPricing(base_price=10.0, default_multiplier=1.5)
    items2 = pricing2.get_billing_items()
    assert len(items2) == 2
    assert items2[0]["description"] == "Base price"
    assert items2[0]["amount"] == 10.0
    assert items2[1]["description"] == "Price multiplier (1.5x)"
    assert items2[1]["amount"] == 5.0  # 10.0 * (1.5 - 1.0)

    # With custom multiplier
    pricing3 = DynamicPricing(base_price=10.0, default_multiplier=1.0)
    items3 = pricing3.get_billing_items(custom_multiplier=2.0)
    assert len(items3) == 2
    assert items3[0]["description"] == "Base price"
    assert items3[1]["description"] == "Price multiplier (2.0x)"
    assert items3[1]["amount"] == 10.0  # 10.0 * (2.0 - 1.0)


def test_dynamic_pricing_edge_cases():
    """Test edge cases for dynamic pricing."""
    # Zero base price
    pricing1 = DynamicPricing(
        base_price=0.0, default_multiplier=1.5, tax_rate=0.1)
    price1 = pricing1.calculate_price()
    assert price1 == 0.0  # 0.0 * 1.5 + 10% tax = 0

    # Zero multiplier
    pricing2 = DynamicPricing(
        base_price=10.0, default_multiplier=0.0, tax_rate=0.1)
    price2 = pricing2.calculate_price()
    assert price2 == 0.0  # 10.0 * 0.0 + 10% tax = 0

    # Negative multiplier (should not be used in practice, but testing behavior)
    pricing3 = DynamicPricing(
        base_price=10.0, default_multiplier=-0.5, tax_rate=0.1)
    price3 = pricing3.calculate_price()
    assert price3 == -5.5  # 10.0 * -0.5 + 10% tax

    # Very large multiplier
    pricing4 = DynamicPricing(
        base_price=10.0, default_multiplier=1000.0, tax_rate=0.1)
    price4 = pricing4.calculate_price()
    assert price4 == 11000.0  # 10.0 * 1000.0 + 10% tax
