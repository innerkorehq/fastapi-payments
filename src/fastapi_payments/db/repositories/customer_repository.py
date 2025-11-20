"""Customer repository."""

from __future__ import annotations

from typing import Dict, Any, List, Optional

from sqlalchemy import select, or_
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Customer, ProviderCustomer


class CustomerRepository:
    """Repository for customer operations backed by SQLAlchemy."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        email: str,
        name: Optional[str] = None,
        meta_info: Optional[Dict[str, Any]] = None,
    ) -> Customer:
        customer = Customer(email=email, name=name, meta_info=meta_info or {})
        self.session.add(customer)
        await self.session.commit()
        await self.session.refresh(customer)
        return customer

    async def update(self, customer_id: str, **fields: Any) -> Optional[Customer]:
        customer = await self.get_by_id(customer_id)
        if not customer:
            return None
        for attr, value in fields.items():
            if value is not None and hasattr(customer, attr):
                setattr(customer, attr, value)
        self.session.add(customer)
        await self.session.commit()
        await self.session.refresh(customer)
        return customer

    async def get_by_id(self, customer_id: str) -> Optional[Customer]:
        return await self.session.get(Customer, customer_id)

    async def add_provider_customer(
        self, customer_id: str, provider: str, provider_customer_id: str
    ) -> ProviderCustomer:
        link = ProviderCustomer(
            customer_id=customer_id,
            provider=provider,
            provider_customer_id=provider_customer_id,
        )
        self.session.add(link)
        await self.session.commit()
        await self.session.refresh(link)
        return link

    async def get_provider_customers(self, customer_id: str) -> List[ProviderCustomer]:
        stmt = select(ProviderCustomer).where(ProviderCustomer.customer_id == customer_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_with_provider_customers(self, customer_id: str) -> Optional[Customer]:
        stmt = (
            select(Customer)
            .options(joinedload(Customer.provider_customers))
            .where(Customer.id == customer_id)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_provider_customer(
        self, customer_id: str, provider: str
    ) -> Optional[ProviderCustomer]:
        stmt = select(ProviderCustomer).where(
            ProviderCustomer.customer_id == customer_id,
            ProviderCustomer.provider == provider,
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        search: Optional[str] = None,
        include_provider_customers: bool = True,
    ) -> List[Customer]:
        """List customers with optional search and pagination."""

        stmt = select(Customer)
        if include_provider_customers:
            stmt = stmt.options(joinedload(Customer.provider_customers))

        if search:
            pattern = f"%{search}%"
            stmt = stmt.where(
                or_(
                    Customer.email.ilike(pattern),
                    Customer.name.ilike(pattern),
                )
            )

        stmt = stmt.order_by(Customer.created_at.desc())
        if offset:
            stmt = stmt.offset(offset)
        if limit:
            stmt = stmt.limit(limit)

        result = await self.session.execute(stmt)
        return result.scalars().all()
