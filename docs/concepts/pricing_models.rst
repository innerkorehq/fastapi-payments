Pricing Models
============

Overview
-------

FastAPI Payments supports various pricing models through its pricing strategies. Each strategy handles price calculations, prorations, billing items, and plan change validations.

The Pricing Strategy Interface
----------------------------

All pricing strategies implement this common interface:

- ``calculate_price``: Calculate the price based on model-specific parameters
- ``calculate_proration``: Calculate prorated amounts for plan changes
- ``get_billing_items``: Generate line items for bills/invoices
- ``validate_plan_change``: Validate if a plan change is allowed

Supported Pricing Models
----------------------

Subscription Pricing
^^^^^^^^^^^^^^^^^

Fixed recurring payments with these features:

- Different billing intervals (monthly, yearly, etc.)
- Quantity-based pricing (e.g., number of licenses)
- Discounts and proration
- Tax calculation

Example:

.. code-block:: python

   # Calculate subscription price
   price = await subscription_pricing.calculate_price(
       base_amount=10.0,
       quantity=5,
       discount_percentage=0.1
   )
   # 10.0 * 5 = 50.0
   # 50.0 * (1-0.1) = 45.0
   # With 20% tax: 45.0 * 1.2 = 54.0

Usage-Based Pricing
^^^^^^^^^^^^^^^^

Pay-as-you-go model with these features:

- Per-unit pricing
- Minimum and maximum charges
- Volume-based discounts
- Usage tracking and aggregation

Example:

.. code-block:: python

   # Calculate usage-based price
   price = await usage_based_pricing.calculate_price(
       unit_price=0.05,
       usage_quantity=1000,
       minimum_charge=10.0
   )
   # 0.05 * 1000 = 50.0
   # min(10.0, 50.0) = 50.0
   # With 20% tax: 50.0 * 1.2 = 60.0

Tiered Pricing
^^^^^^^^^^^^

Pricing that changes based on usage tiers:

- Multiple pricing tiers
- Different rates per tier
- Flat fees per tier
- Graduated or volume pricing

Example:

.. code-block:: python

   # Define tiers
   tiers = [
       {"lower_bound": 0, "upper_bound": 1000, "price_per_unit": 0.05, "flat_fee": 10},
       {"lower_bound": 1000, "upper_bound": 10000, "price_per_unit": 0.03, "flat_fee": 0},
       {"lower_bound": 10000, "upper_bound": None, "price_per_unit": 0.01, "flat_fee": 0}
   ]
   
   # Calculate tiered price for 1500 units
   price = await tiered_pricing.calculate_price(tiers=tiers, quantity=1500)
   # Tier 1: 10 + (0.05 * 1000) = 60.0
   # Tier 2: 0 + (0.03 * 500) = 15.0
   # Total: 60.0 + 15.0 = 75.0
   # With 20% tax: 75.0 * 1.2 = 90.0

Per-User Pricing
^^^^^^^^^^^^^

Seat-based pricing for multi-user systems:

- Per-seat pricing
- Volume discounts based on user count
- Minimum seat requirements
- User-based tiers

Example:

.. code-block:: python

   # Calculate per-user price
   price = await per_user_pricing.calculate_price(
       base_amount=10.0,
       num_users=20,
       discount_tiers=[
           {"min_users": 20, "discount_percentage": 0.2},
           {"min_users": 10, "discount_percentage": 0.1},
           {"min_users": 5, "discount_percentage": 0.05}
       ]
   )
   # 10.0 * 20 = 200.0
   # 200.0 * (1-0.2) = 160.0
   # With 20% tax: 160.0 * 1.2 = 192.0

Freemium Pricing
^^^^^^^^^^^^^

Free tier with premium upgrades:

- Free usage within limits
- Paid tier when limits are exceeded
- Clear upgrade/downgrade paths
- Usage tracking against free limits

Example:

.. code-block:: python

   # Calculate freemium price
   price = await freemium_pricing.calculate_price(
       base_amount=20.0,
       usage_metrics={"api_calls": 1200, "storage_gb": 0.5},
       free_tier_limits={"api_calls": 1000, "storage_gb": 1}
   )
   # User exceeds API calls limit, so they pay full price
   # 20.0 with 20% tax: 24.0

Dynamic Pricing
^^^^^^^^^^^^

Price adjusts based on factors like demand:

- Variable pricing based on conditions
- Time-based pricing fluctuations
- Demand-based multipliers
- Market-based adjustments

Hybrid Pricing
^^^^^^^^^^^

Combines multiple pricing models:

- Base subscription + usage charges
- Tiered pricing with per-user components
- Complex pricing rules
- Multiple revenue streams in one plan

Pricing Configuration
------------------

Configure pricing behavior with these settings:

.. code-block:: json

   {
     "pricing": {
       "default_currency": "USD",
       "default_pricing_model": "subscription",
       "round_to_decimal_places": 2,
       "allow_custom_pricing": true,
       "tax": {
         "default_rate": 0.2,
         "included_in_price": false,
         "use_tax_service": false
       }
     }
   }