"""Repository for payment method persistence."""

from __future__ import annotations

from typing import Any, Optional, List

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import PaymentMethod


class PaymentMethodRepository:
    """Repository for storing and querying saved payment methods."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        customer_id: str,
        provider: str,
        provider_payment_method_id: str,
        mandate_id: Optional[str] = None,
        is_default: bool = False,
        card_brand: Optional[str] = None,
        card_last4: Optional[str] = None,
        card_exp_month: Optional[int] = None,
        card_exp_year: Optional[int] = None,
        meta_info: Optional[dict[str, Any]] = None,
    ) -> PaymentMethod:
        pm = PaymentMethod(
            customer_id=customer_id,
            provider=provider,
            provider_payment_method_id=provider_payment_method_id,
            mandate_id=mandate_id,
            is_default=is_default,
            card_brand=card_brand,
            card_last4=card_last4,
            card_exp_month=card_exp_month,
            card_exp_year=card_exp_year,
            meta_info=meta_info or {},
        )
        self.session.add(pm)
        await self.session.commit()
        await self.session.refresh(pm)
        return pm

    async def get_by_id(self, method_id: str) -> Optional[PaymentMethod]:
        return await self.session.get(PaymentMethod, method_id)

    async def get_by_provider_method_id(
        self, provider: Optional[str], provider_method_id: str
    ) -> Optional[PaymentMethod]:
        # If provider is provided, filter by both provider and provider_method_id.
        # Otherwise search across providers for a matching provider_payment_method_id.
        if provider:
            stmt = select(PaymentMethod).where(
                PaymentMethod.provider == provider,
                PaymentMethod.provider_payment_method_id == provider_method_id,
            )
        else:
            stmt = select(PaymentMethod).where(
                PaymentMethod.provider_payment_method_id == provider_method_id
            )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_for_customer(
        self,
        customer_id: str,
        provider: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[PaymentMethod]:
        stmt = select(PaymentMethod).where(PaymentMethod.customer_id == customer_id)
        if provider:
            stmt = stmt.where(PaymentMethod.provider == provider)
        stmt = stmt.order_by(PaymentMethod.created_at.desc())
        if offset:
            stmt = stmt.offset(offset)
        if limit:
            stmt = stmt.limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def update(self, method_id: str, **fields: Any) -> Optional[PaymentMethod]:
        pm = await self.get_by_id(method_id)
        if not pm:
            return None

        for attr, value in fields.items():
            if hasattr(pm, attr):
                setattr(pm, attr, value)

        self.session.add(pm)
        await self.session.commit()
        await self.session.refresh(pm)
        return pm

    async def delete(self, method_id: str) -> bool:
        """Delete a stored PaymentMethod from the database.

        Returns True if a row was deleted, False otherwise.
        """
        pm = await self.get_by_id(method_id)
        if not pm:
            return False

        await self.session.delete(pm)
        await self.session.commit()
        return True

    async def set_default(self, customer_id: str, method_id: str) -> Optional[PaymentMethod]:
        # Unset any existing default methods for this customer
        await self.session.execute(
            update(PaymentMethod)
            .where(PaymentMethod.customer_id == customer_id)
            .values(is_default=False)
        )
        await self.session.commit()

        return await self.update(method_id, is_default=True)
