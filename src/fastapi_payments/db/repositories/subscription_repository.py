"""Subscription repository."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Subscription


class SubscriptionRepository:
    """Repository for subscription operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        customer_id: str,
        plan_id: str,
        provider: str,
        provider_subscription_id: str,
        status: str,
        quantity: int,
        current_period_start,
        current_period_end,
        cancel_at_period_end: bool,
        meta_info: Optional[dict[str, Any]] = None,
    ) -> Subscription:
        subscription = Subscription(
            customer_id=customer_id,
            plan_id=plan_id,
            provider=provider,
            provider_subscription_id=provider_subscription_id,
            status=status,
            quantity=quantity,
            current_period_start=current_period_start,
            current_period_end=current_period_end,
            cancel_at_period_end=cancel_at_period_end,
            meta_info=meta_info or {},
        )
        self.session.add(subscription)
        await self.session.commit()
        await self.session.refresh(subscription)
        return subscription

    async def get_with_plan(self, subscription_id: str) -> Optional[Subscription]:
        stmt = (
            select(Subscription)
            .options(joinedload(Subscription.plan))
            .where(Subscription.id == subscription_id)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_id(self, subscription_id: str) -> Optional[Subscription]:
        return await self.session.get(Subscription, subscription_id)

    async def update(self, subscription_id: str, **fields: Any) -> Optional[Subscription]:
        subscription = await self.get_by_id(subscription_id)
        if not subscription:
            return None
        for attr, value in fields.items():
            if hasattr(subscription, attr):
                setattr(subscription, attr, value)
        self.session.add(subscription)
        await self.session.commit()
        await self.session.refresh(subscription)
        return subscription

    async def list(
        self,
        *,
        customer_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        include_plan: bool = True,
    ) -> list[Subscription]:
        stmt = select(Subscription)
        if include_plan:
            stmt = stmt.options(joinedload(Subscription.plan))

        if customer_id:
            stmt = stmt.where(Subscription.customer_id == customer_id)
        if status:
            stmt = stmt.where(Subscription.status == status)

        stmt = stmt.order_by(Subscription.created_at.desc())
        if offset:
            stmt = stmt.offset(offset)
        if limit:
            stmt = stmt.limit(limit)

        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_for_customer(
        self,
        customer_id: str,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Subscription]:
        return await self.list(customer_id=customer_id, limit=limit, offset=offset)
