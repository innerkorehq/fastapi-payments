from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta, timezone
import json
import re
import hashlib
import secrets
import string


def generate_random_string(length: int = 16) -> str:
    """
    Generate a random string of specified length.

    Args:
        length: Length of the random string

    Returns:
        Random string
    """
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def generate_idempotency_key() -> str:
    """
    Generate an idempotency key for API requests.

    Returns:
        Idempotency key
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    random_string = generate_random_string(8)
    return f"idempkey_{timestamp}_{random_string}"


def format_amount(amount: Union[int, float], currency: str) -> int:
    """
    Format amount according to currency's smallest unit.

    Args:
        amount: Amount in decimal form (e.g., 10.99)
        currency: Currency code (e.g., USD)

    Returns:
        Amount in smallest unit (e.g., cents)
    """
    # Currencies with no minor units
    zero_decimal_currencies = [
        "JPY",
        "KRW",
        "VND",
        "BIF",
        "CLP",
        "DJF",
        "GNF",
        "ISK",
        "PYG",
        "RWF",
        "UGX",
        "VUV",
        "XAF",
        "XOF",
        "XPF",
    ]

    if currency.upper() in zero_decimal_currencies:
        return int(amount)
    else:
        return int(amount * 100)


def parse_amount(amount: int, currency: str) -> float:
    """
    Parse amount from smallest unit to decimal form.

    Args:
        amount: Amount in smallest unit (e.g., cents)
        currency: Currency code (e.g., USD)

    Returns:
        Amount in decimal form (e.g., 10.99)
    """
    # Currencies with no minor units
    zero_decimal_currencies = [
        "JPY",
        "KRW",
        "VND",
        "BIF",
        "CLP",
        "DJF",
        "GNF",
        "ISK",
        "PYG",
        "RWF",
        "UGX",
        "VUV",
        "XAF",
        "XOF",
        "XPF",
    ]

    if currency.upper() in zero_decimal_currencies:
        return float(amount)
    else:
        return amount / 100


def sanitize_meta_info(meta_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize meta_info to ensure it only contains supported types.

    Args:
        meta_info: Raw meta_info dictionary

    Returns:
        Sanitized meta_info dictionary
    """
    if not meta_info:
        return {}

    # Convert to JSON and back to ensure serializable
    try:
        sanitized = json.loads(json.dumps(meta_info))

        # Ensure meta_info keys are valid
        result = {}
        for key, value in sanitized.items():
            # Ensure keys are strings and don't contain invalid characters
            if isinstance(key, str) and re.match(r"^[a-zA-Z0-9_\-]+$", key):
                result[key] = value

        return result
    except (TypeError, ValueError):
        # If meta_info can't be serialized, return empty dict
        return {}


def sanitize_metadata(metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Sanitize metadata to ensure it's valid and safe to store or transmit.

    Args:
        metadata: Optional dictionary of metadata

    Returns:
        Sanitized metadata dictionary (empty dict if input was None)
    """
    if metadata is None:
        return {}

    if not isinstance(metadata, dict):
        raise ValueError("Metadata must be a dictionary")

    # Create a new dict with sanitized values
    sanitized = {}

    for key, value in metadata.items():
        # Skip None values
        if value is None:
            continue

        # Convert keys to strings and ensure they only contain valid characters
        str_key = str(key)

        # Only allow alphanumeric, underscore, and dash in keys
        if not re.match(r"^[a-zA-Z0-9_\-]+$", str_key):
            continue

        # Handle nested dictionaries recursively
        if isinstance(value, dict):
            sanitized[str_key] = sanitize_metadata(value)
        # Handle lists (ensure all items are serializable)
        elif isinstance(value, list):
            sanitized[str_key] = [
                sanitize_metadata(item) if isinstance(item, dict) else item
                for item in value
            ]
        # Handle all other types - ensure they're JSON serializable
        else:
            try:
                # Test if it's JSON serializable
                json.dumps({str_key: value})
                sanitized[str_key] = value
            except (TypeError, OverflowError):
                # If not serializable, convert to string
                sanitized[str_key] = str(value)

    return sanitized


def calculate_subscription_period_end(
    period_start: datetime, interval: str, interval_count: int = 1
) -> datetime:
    """
    Calculate subscription period end date.

    Args:
        period_start: Period start date
        interval: Billing interval (day, week, month, year)
        interval_count: Number of intervals

    Returns:
        Period end date
    """
    if interval.lower() == "day":
        return period_start + timedelta(days=interval_count)
    elif interval.lower() == "week":
        return period_start + timedelta(weeks=interval_count)
    elif interval.lower() == "month":
        # Add months manually since timedelta doesn't support months
        year = period_start.year
        month = period_start.month + interval_count

        # Adjust year if months overflow
        while month > 12:
            year += 1
            month -= 12

        # Handle day overflow (e.g., Jan 31 + 1 month)
        day = min(
            period_start.day,
            [
                31,
                29 if is_leap_year(year) else 28,
                31,
                30,
                31,
                30,
                31,
                31,
                30,
                31,
                30,
                31,
            ][month - 1],
        )

        return period_start.replace(year=year, month=month, day=day)
    elif interval.lower() == "year":
        # Add years
        return period_start.replace(year=period_start.year + interval_count)
    else:
        raise ValueError(f"Unsupported interval: {interval}")


def is_leap_year(year: int) -> bool:
    """
    Check if a year is a leap year.

    Args:
        year: Year to check

    Returns:
        True if leap year, False otherwise
    """
    return (year % 4 == 0) and (year % 100 != 0 or year % 400 == 0)


def normalize_webhook_event(
    provider: str, event_type: str, payload: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Normalize webhook event data across different providers.

    Args:
        provider: Provider name
        event_type: Provider-specific event type
        payload: Event payload

    Returns:
        Normalized event data
    """
    # Generic event data structure
    event = {
        "provider": provider,
        "original_event_type": event_type,
        "event_type": None,  # Will be set based on mapping
        "object_type": None,  # payment, subscription, etc.
        "object_id": None,  # ID of the relevant object
        "status": None,  # Status of the object
        "customer_id": None,  # Customer ID if available
        "created": datetime.now(timezone.utc).isoformat(),
        "data": payload,  # Original payload
    }

    # Provider-specific normalization
    if provider == "stripe":
        event["object_type"] = payload.get("object", {}).get("object")
        event["object_id"] = payload.get("object", {}).get("id")

        # Map Stripe events to normalized types
        if "payment_intent.succeeded" in event_type:
            event["event_type"] = "payment.succeeded"
            event["status"] = "succeeded"
        elif "payment_intent.payment_failed" in event_type:
            event["event_type"] = "payment.failed"
            event["status"] = "failed"
        elif "invoice.payment_succeeded" in event_type:
            event["event_type"] = "invoice.paid"
            event["status"] = "paid"
        elif "customer.subscription.created" in event_type:
            event["event_type"] = "subscription.created"
            event["status"] = payload.get("object", {}).get("status")
        # Add more Stripe event mappings as needed

    elif provider == "paypal":
        if "PAYMENT.CAPTURE.COMPLETED" in event_type:
            event["event_type"] = "payment.succeeded"
            event["object_type"] = "payment"
            event["status"] = "completed"
        # Add more PayPal event mappings as needed

    elif provider == "adyen":
        notification = payload.get("NotificationRequestItem", {})
        event["object_id"] = notification.get("pspReference")

        if event_type == "AUTHORISATION":
            event["event_type"] = "payment.authorized"
            event["object_type"] = "payment"
            event["status"] = "authorized"
        elif event_type == "CAPTURE":
            event["event_type"] = "payment.succeeded"
            event["object_type"] = "payment"
            event["status"] = "succeeded"
        # Add more Adyen event mappings as needed

    return event
