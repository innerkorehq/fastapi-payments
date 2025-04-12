"""Plan repository."""

from sqlalchemy.ext.asyncio import AsyncSession


class PlanRepository:
    """Repository for plan operations."""

    def __init__(self, session: AsyncSession):
        """
        Initialize the repository.

        Args:
            session: SQLAlchemy AsyncSession
        """
        self.session = session
