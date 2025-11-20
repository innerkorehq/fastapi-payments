"""Provider factory and utilities."""

from typing import Dict, Any, Optional
import importlib
import logging

from .base import PaymentProvider
from .stripe import StripeProvider

# Import other providers conditionally to avoid dependency issues

logger = logging.getLogger(__name__)


def get_provider(
    provider_name: str, provider_config: Dict[str, Any]
) -> PaymentProvider:
    """
    Factory function to get a payment provider instance.

    Args:
        provider_name: Name of the provider (stripe, paypal, etc.)
        provider_config: Configuration for the provider

    Returns:
        A PaymentProvider instance

    Raises:
        ValueError: If provider is not supported or configuration is invalid
    """
    provider_name = provider_name.lower()

    # Try to get provider class from additional settings if specified
    provider_class = None
    if (
        hasattr(provider_config, "additional_settings")
        and provider_config.additional_settings
    ):
        provider_class_path = provider_config.additional_settings.get(
            "provider_class")
        if provider_class_path:
            try:
                module_path, class_name = provider_class_path.rsplit(".", 1)
                module = importlib.import_module(module_path)
                provider_class = getattr(module, class_name)
            except (ImportError, AttributeError) as e:
                logger.error(
                    f"Could not load custom provider class {provider_class_path}: {str(e)}"
                )

    # If no custom class or loading failed, use built-in providers
    if provider_class is None:
        if provider_name == "stripe":
            provider_class = StripeProvider

        elif provider_name == "paypal":
            try:
                from .paypal import PayPalProvider

                provider_class = PayPalProvider
            except ImportError:
                raise ValueError(
                    "PayPal provider requested but dependencies not available. "
                    "Install with 'pip install \"fastapi-payments[paypal]\"'"
                )

        elif provider_name == "adyen":
            try:
                from .adyen import AdyenProvider

                provider_class = AdyenProvider
            except ImportError:
                raise ValueError(
                    "Adyen provider requested but dependencies not available. "
                    "Install with 'pip install \"fastapi-payments[adyen]\"'"
                )

        elif provider_name == "payu":
            from .payu import PayUProvider

            provider_class = PayUProvider

        else:
            raise ValueError(f"Unsupported payment provider: {provider_name}")

    # Create and return provider instance
    provider = provider_class(provider_config)
    logger.info(f"Initialized {provider_name} payment provider")

    return provider
