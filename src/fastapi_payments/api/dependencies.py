from typing import Callable, AsyncGenerator
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..config.config_schema import PaymentConfig
from ..services.payment_service import PaymentService
from ..messaging.publishers import PaymentEventPublisher
from ..db.repositories import get_db as get_db_session

# Global instances that will be initialized at app startup
_config = None
_payment_service = None
_event_publisher = None


def set_config(config: PaymentConfig):
    """
    Set the payment configuration.

    This is a simpler version of initialize_dependencies that only sets the config.
    It's used during module initialization in __init__.py.

    Args:
        config: Payment configuration object
    """
    global _config
    _config = config


def initialize_dependencies(config: PaymentConfig):
    """Initialize global dependencies."""
    global _config, _payment_service, _event_publisher
    set_config(config)  # Use set_config to maintain consistency
    _event_publisher = PaymentEventPublisher(config.messaging)
    _payment_service = PaymentService(
        config, _event_publisher, None
    )  # No DB session yet


async def get_config():
    """Get the payment configuration."""
    if _config is None:
        raise RuntimeError(
            "Dependencies not initialized. Call initialize_dependencies first."
        )
    return _config


async def get_payment_service():
    """Get the payment service."""
    if _payment_service is None:
        raise RuntimeError(
            "Dependencies not initialized. Call initialize_dependencies first."
        )
    return _payment_service


# New dependency that combines DB session with payment service
async def get_payment_service_with_db(
    payment_service: PaymentService = Depends(get_payment_service),
    db: AsyncSession = Depends(get_db_session),
) -> PaymentService:
    """
    Get payment service with database session.

    This dependency handles setting the DB session on the payment service,
    so route handlers don't need to do it manually.
    """
    payment_service.set_db_session(db)
    return payment_service


# Keep the original get_db available for direct use
get_db = get_db_session
