"""Payment repository."""

from sqlalchemy.ext.asyncio import AsyncSession


class PaymentRepository:
    """Repository for payment operations."""

    def __init__(self, session: AsyncSession):
        """
        Initialize the repository.

        Args:
            session: SQLAlchemy AsyncSession
        """
        self.session = session
