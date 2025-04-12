"""Product repository."""

from sqlalchemy.ext.asyncio import AsyncSession


class ProductRepository:
    """Repository for product operations."""

    def __init__(self, session: AsyncSession):
        """
        Initialize the repository.

        Args:
            session: SQLAlchemy AsyncSession
        """
        self.session = session
