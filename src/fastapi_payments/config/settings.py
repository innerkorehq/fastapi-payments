from pathlib import Path
from typing import Dict, Any, Optional, Union
import json
import os
import logging
from .config_schema import PaymentConfig

logger = logging.getLogger(__name__)


def load_config_from_file(file_path: Union[str, Path]) -> Dict[str, Any]:
    """
    Load configuration from a JSON file.

    Args:
        file_path: Path to JSON configuration file

    Returns:
        Configuration dictionary

    Raises:
        FileNotFoundError: If the configuration file doesn't exist
        json.JSONDecodeError: If the configuration file is not valid JSON
    """
    file_path = Path(file_path) if isinstance(file_path, str) else file_path

    if not file_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {file_path}")

    with open(file_path, "r") as f:
        config = json.load(f)

    logger.info(f"Configuration loaded from {file_path}")
    return config


def load_config_from_env() -> Dict[str, Any]:
    """
    Load configuration from environment variables.

    Environment variables should be prefixed with PAYMENT_
    For nested keys, use double underscore as separator

    Examples:
    - PAYMENT_DEFAULT_PROVIDER=stripe
    - PAYMENT_DATABASE__URL=postgresql://user:pass@localhost/db
    - PAYMENT_PROVIDERS__STRIPE__API_KEY=sk_test_123

    Returns:
        Configuration dictionary
    """
    config = {}

    # Find all environment variables with the PAYMENT_ prefix
    payment_vars = {k: v for k, v in os.environ.items()
                    if k.startswith("PAYMENT_")}

    for key, value in payment_vars.items():
        # Remove prefix and split by double underscore
        key = key[8:]  # Remove "PAYMENT_"
        parts = key.lower().split("__")

        # Build nested configuration
        current = config
        for i, part in enumerate(parts):
            if i == len(parts) - 1:
                # Convert value types
                if value.lower() == "true":
                    current[part] = True
                elif value.lower() == "false":
                    current[part] = False
                elif value.isdigit():
                    current[part] = int(value)
                elif value.replace(".", "", 1).isdigit() and value.count(".") < 2:
                    current[part] = float(value)
                else:
                    current[part] = value
            else:
                if part not in current:
                    current[part] = {}
                current = current[part]

    logger.info("Configuration loaded from environment variables")
    return config


def merge_configs(
    base_config: Dict[str, Any], override_config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Merge two configuration dictionaries with the override taking precedence.

    Args:
        base_config: Base configuration
        override_config: Override configuration

    Returns:
        Merged configuration dictionary
    """
    result = base_config.copy()

    for key, value in override_config.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_configs(result[key], value)
        else:
            result[key] = value

    return result


def load_config(
    file_path: Optional[Union[str, Path]] = None,
    env_override: bool = True,
    validate: bool = True,
) -> Union[PaymentConfig, Dict[str, Any]]:
    """
    Load and validate payment configuration.

    Args:
        file_path: Optional path to JSON configuration file
        env_override: Whether to override with environment variables
        validate: Whether to validate and return a PaymentConfig instance

    Returns:
        PaymentConfig if validate=True, otherwise a configuration dictionary

    Raises:
        FileNotFoundError: If the configuration file doesn't exist
        json.JSONDecodeError: If the configuration file is not valid JSON
        ValidationError: If validation is enabled and the configuration is invalid
    """
    config = {}

    # Load from file if provided
    if file_path:
        config = load_config_from_file(file_path)

    # Override with environment variables if enabled
    if env_override:
        env_config = load_config_from_env()
        config = merge_configs(config, env_config)

    # Validate and return PaymentConfig instance if enabled
    if validate:
        return PaymentConfig(**config)

    return config
