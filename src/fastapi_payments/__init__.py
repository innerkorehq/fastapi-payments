from fastapi import FastAPI, APIRouter
from .config.config_schema import PaymentConfig
from .db.repositories import initialize_db
from .api.routes import router as payment_router
from .api.dependencies import set_config
import logging


class FastAPIPayments:
    """Main class for FastAPI Payments integration."""

    def __init__(self, config: dict):
        """
        Initialize the FastAPI Payments module.

        Args:
            config: Configuration dictionary or PaymentConfig instance
        """
        # Convert dict to PaymentConfig if needed
        if isinstance(config, dict):
            self.config = PaymentConfig(**config)
        else:
            self.config = config

        # Set up logging
        level = getattr(logging, self.config.logging_level)
        logging.basicConfig(level=level)
        self.logger = logging.getLogger("fastapi_payments")

        # Set config in dependency injection
        set_config(self.config)

        # Initialize database
        try:
            initialize_db(self.config.database)
            self.logger.info("Database initialized successfully")
        except Exception as e:
            self.logger.error(f"Error initializing database: {str(e)}")
            if self.config.debug_mode:
                raise

        self.logger.info("FastAPI Payments initialized")

    def include_router(self, app: FastAPI, prefix: str = "/payments"):
        """
        Include payment routes in a FastAPI application.

        Args:
            app: FastAPI application
            prefix: URL prefix for payment routes
        """
        app.include_router(payment_router, prefix=prefix)
        self.logger.info(f"Payment routes added with prefix: {prefix}")


def create_payment_module(config: dict):
    """
    Create a FastAPI Payments module.

    Args:
        config: Configuration dictionary

    Returns:
        FastAPIPayments instance
    """
    return FastAPIPayments(config)
