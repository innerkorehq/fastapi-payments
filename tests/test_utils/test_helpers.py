import pytest
from datetime import datetime, timedelta, timezone
import re

from fastapi_payments.utils.helpers import (
    generate_random_string,
    generate_idempotency_key,
    format_amount,
    parse_amount,
    sanitize_metadata,
    calculate_subscription_period_end,
)


def test_generate_random_string():
    """Test generating random strings."""
    # Test default length
    random_str = generate_random_string()
    assert len(random_str) == 16
    assert isinstance(random_str, str)

    # Test custom length
    random_str = generate_random_string(length=8)
    assert len(random_str) == 8

    # Uniqueness
    string1 = generate_random_string()
    string3 = generate_random_string()
    assert string1 != string3


def test_generate_idempotency_key():
    """Test generating idempotency keys for API requests."""
    idempotency_key = generate_idempotency_key()
    assert idempotency_key.startswith("idempkey_")

    # Should have format: idempkey_<timestamp>_<random>
    parts = idempotency_key.split("_")
    assert len(parts) == 3

    # Validate timestamp format
    timestamp_str = parts[1]
    assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", timestamp_str)

    # Third part should be a random string
    assert len(parts[2]) > 0


def test_format_amount():
    """Test formatting amounts according to currency."""
    # Test standard currencies
    assert format_amount(10.99, "USD") == 1099  # USD has cents
    assert format_amount(10.99, "EUR") == 1099  # EUR has cents
    assert format_amount(10.99, "GBP") == 1099
    assert format_amount(0.01, "USD") == 1

    # Test zero-decimal currencies
    assert format_amount(10.99, "JPY") == 10  # JPY has no cents
    assert format_amount(10.99, "KRW") == 10
    assert format_amount(10.00, "JPY") == 10


def test_parse_amount():
    """Test parsing amounts from minor to major units."""
    # Test standard currencies
    assert parse_amount(1099, "USD") == 10.99  # USD has cents
    assert parse_amount(1099, "EUR") == 10.99  # EUR has cents
    assert parse_amount(50, "USD") == 0.50

    # Test zero-decimal currencies
    assert parse_amount(1099, "JPY") == 1099.0  # JPY has no cents
    assert parse_amount(1099, "KRW") == 1099.0
    assert parse_amount(10, "JPY") == 10.0


def test_sanitize_metadata():
    """Test sanitizing metadata."""
    # Test with valid metadata
    metadata = {
        "key1": "value1",
        "key2": 123,
        "nested": {"subkey": "subvalue"},
        "invalid/key": "value2",  # Should be removed
    }

    result = sanitize_metadata(metadata)

    # Check that valid keys remain
    assert "key1" in result
    assert "key2" in result
    assert "nested" in result

    # Check that invalid keys are removed
    assert "invalid/key" not in result

    # Check that nested dictionaries are processed
    assert isinstance(result["nested"], dict)
    assert result["nested"]["subkey"] == "subvalue"


def test_sanitize_metadata_edge_cases():
    """Test sanitizing metadata edge cases."""
    # Test with None
    assert sanitize_metadata(None) == {}

    # Test with non-dict
    with pytest.raises(ValueError):
        sanitize_metadata("not a dict")

    # Test with empty dict
    assert sanitize_metadata({}) == {}

    # Test with non-serializable values
    metadata = {
        "key1": "value1",
        "key2": datetime.now(
            timezone.utc
        ),  # Datetime is not directly JSON-serializable
    }
    result = sanitize_metadata(metadata)
    assert "key1" in result
    assert "key2" in result
    assert isinstance(result["key2"], str)  # Should be converted to string


def test_calculate_subscription_period_end():
    """Test calculating subscription period end dates."""
    start_date = datetime(2025, 1, 15)

    # Daily
    daily_end = calculate_subscription_period_end(start_date, "day", 5)
    assert daily_end == start_date + timedelta(days=5)

    # Weekly
    weekly_end = calculate_subscription_period_end(start_date, "week", 2)
    assert weekly_end == start_date + timedelta(weeks=2)

    # Monthly
    monthly_end = calculate_subscription_period_end(start_date, "month", 1)
    assert monthly_end == datetime(2025, 2, 15)

    # Multi-month
    multi_month_end = calculate_subscription_period_end(start_date, "month", 3)
    assert multi_month_end == datetime(2025, 4, 15)

    # Yearly
    yearly_end = calculate_subscription_period_end(start_date, "year", 1)
    assert yearly_end == datetime(2026, 1, 15)

    # Leap year handling (Jan 31 + 1 month = Feb 28/29)
    leap_year_start = datetime(2024, 1, 31)  # 2024 is a leap year
    leap_year_end = calculate_subscription_period_end(
        leap_year_start, "month", 1)
    assert leap_year_end == datetime(2024, 2, 29)

    # Non-leap year handling
    non_leap_year_start = datetime(2025, 1, 31)  # 2025 is not a leap year
    non_leap_year_end = calculate_subscription_period_end(
        non_leap_year_start, "month", 1
    )
    assert non_leap_year_end == datetime(2025, 2, 28)
