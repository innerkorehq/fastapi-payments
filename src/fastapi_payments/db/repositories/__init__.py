"""Database repositories package."""

import asyncio
from typing import Optional, AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, AsyncEngine
from sqlalchemy.orm import sessionmaker

from ...config.config_schema import DatabaseConfig
from ..models import Base
from .base import BaseRepository
from .customer_repository import CustomerRepository
from .payment_repository import PaymentRepository
from .payment_method_repository import PaymentMethodRepository
from .subscription_repository import SubscriptionRepository
from .product_repository import ProductRepository
from .plan_repository import PlanRepository
from .sync_job_repository import SyncJobRepository

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

    # Defer schema creation to avoid event loop issues in multiprocessing
    # Schema will be created on first database access
    return _engine


def _create_schema_sync(engine: AsyncEngine) -> None:
    """Create database schema using the async engine from any context."""

    async def _create_schema():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    try:
        loop = asyncio.get_running_loop()
        # If we're in a running loop, try to run the task in it
        if loop.is_running():
            # Schedule the task and wait for it
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, _create_schema())
                future.result()  # Wait for completion
        else:
            loop.run_until_complete(_create_schema())
    except RuntimeError:
        # No loop running, use asyncio.run
        asyncio.run(_create_schema())


async def _create_schema_async(engine: AsyncEngine) -> None:
    """Create database schema asynchronously."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Get a database session.

    Returns:
        AsyncGenerator yielding an SQLAlchemy AsyncSession
    """
    if _sessionmaker is None:
        raise RuntimeError("Database not initialized")

    # Create schema on first access if not already done
    if not hasattr(get_db, '_schema_created'):
        await _create_schema_async(_engine)
        get_db._schema_created = True

    # Use the sessionmaker async context to manage the session lifecycle. The
    # context manager will close the session for us when the dependency exits.
    async with _sessionmaker() as session:
        yield session


# Export repository classes
__all__ = [
    "initialize_db",
    "get_db",
    "BaseRepository",
    "CustomerRepository",
    "PaymentRepository",
    "SubscriptionRepository",
    "ProductRepository",
    "PlanRepository",
    "PaymentMethodRepository",
    "SyncJobRepository",
]
