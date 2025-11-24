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
        address: Optional[Dict[str, Any]] = None,
    ) -> Customer:
        # If an address exists inside meta_info but address param is empty,
        # move it into the dedicated address column for structured queries.
        meta_info = dict(meta_info or {})
        if address:
            if isinstance(meta_info.get("address"), dict):
                # remove duplicate from meta_info
                meta_info.pop("address", None)
        else:
            if isinstance(meta_info.get("address"), dict):
                address = meta_info.pop("address")

        customer = Customer(email=email, name=name, meta_info=meta_info or {}, address=address)
        self.session.add(customer)
        await self.session.commit()
        await self.session.refresh(customer)
        return customer

    async def update(self, customer_id: str, **fields: Any) -> Optional[Customer]:
        customer = await self.get_by_id(customer_id)
        if not customer:
            return None
        # Normalize address vs meta_info.address: if meta_info contains address,
        # prefer the explicit address field and remove it from meta_info.
        if "meta_info" in fields and isinstance(fields["meta_info"], dict):
            mi = dict(customer.meta_info or {})
            incoming_mi = dict(fields["meta_info"] or {})
            # If incoming meta_info has address and address field provided is None,
            # move it to address. If the caller explicitly provided address as
            # param then drop the address key from incoming meta_info to avoid
            # duplication.
            if "address" in incoming_mi and not fields.get("address"):
                fields["address"] = incoming_mi.pop("address")
            elif "address" in incoming_mi and fields.get("address") is not None:
                # caller provided address explicitly - remove duplicate
                incoming_mi.pop("address", None)
            # merge remaining meta_info
            mi.update(incoming_mi)
            fields["meta_info"] = mi

        # If an address is being updated but the caller didn't include a
        # meta_info payload, and the existing stored meta_info contains the
        # old address, remove it to prevent duplication
        if "address" in fields and fields.get("address") is not None and "meta_info" not in fields:
            existing_meta = dict(customer.meta_info or {})
            if "address" in existing_meta:
                existing_meta.pop("address", None)
                fields["meta_info"] = existing_meta

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
        # When joined eager-loading against collections, SQLAlchemy returns
        # duplicate parent rows; calling `unique()` on the result collapses
        # duplicate parent objects so `.scalars()` returns unique entities.
        return result.unique().scalars().all()

    async def get_with_provider_customers(self, customer_id: str) -> Optional[Customer]:
        stmt = (
            select(Customer)
            .options(joinedload(Customer.provider_customers))
            .where(Customer.id == customer_id)
        )
        result = await self.session.execute(stmt)
        # The same `unique()` is required when joined-loading collections
        # to ensure a single Customer instance is returned.
        return result.unique().scalars().first()

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
        # Call unique() because we often joinload the provider_customers
        # collection which causes duplicated parent rows for Customers.
        return result.unique().scalars().all()
