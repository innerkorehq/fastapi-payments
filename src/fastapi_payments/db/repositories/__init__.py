"""Database repositories package."""

from typing import Optional, AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, AsyncEngine
from sqlalchemy.orm import sessionmaker

from ...config.config_schema import DatabaseConfig
from .customer_repository import CustomerRepository
from .payment_repository import PaymentRepository
from .subscription_repository import SubscriptionRepository
from .product_repository import ProductRepository
from .plan_repository import PlanRepository

# Global engine
_engine: Optional[AsyncEngine] = None
_sessionmaker = None


def initialize_db(config: DatabaseConfig) -> AsyncEngine:
    """Initialize the database connection."""
    global _engine, _sessionmaker

    # Create engine with appropriate parameters based on dialect
    if config.url.startswith("sqlite"):
        # SQLite doesn't support connection pooling parameters
        _engine = create_async_engine(config.url, echo=config.echo)
    else:
        # Use connection pool parameters for other database engines
        _engine = create_async_engine(
            config.url,
            echo=config.echo,
            pool_size=getattr(config, "pool_size", 5),
            max_overflow=getattr(config, "max_overflow", 10),
        )

    # Create sessionmaker
    _sessionmaker = sessionmaker(
        _engine, class_=AsyncSession, expire_on_commit=False)

    return _engine


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Get a database session.

    Returns:
        AsyncGenerator yielding an SQLAlchemy AsyncSession
    """
    if _sessionmaker is None:
        raise RuntimeError("Database not initialized")

    async with _sessionmaker() as session:
        try:
            yield session
        finally:
            await session.close()


# Export repository classes
__all__ = [
    "initialize_db",
    "get_db",
    "CustomerRepository",
    "PaymentRepository",
    "SubscriptionRepository",
    "ProductRepository",
    "PlanRepository",
]
