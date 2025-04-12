"""Subscription repository."""

from sqlalchemy.ext.asyncio import AsyncSession


class SubscriptionRepository:
    """Repository for subscription operations."""

    def __init__(self, session: AsyncSession):
        """
        Initialize the repository.

        Args:
            session: SQLAlchemy AsyncSession
        """
        self.session = session
