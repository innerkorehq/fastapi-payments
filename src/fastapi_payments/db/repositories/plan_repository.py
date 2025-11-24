"""Plan repository."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Plan, PricingModel


def _coerce_pricing_model(value: Any) -> PricingModel:
    if isinstance(value, PricingModel):
        return value
    if not isinstance(value, str):
        raise ValueError("pricing_model must be a string or PricingModel enum")
    normalized = value.lower()
    return PricingModel(normalized)


class PlanRepository:
    """Repository for plan persistence."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        product_id: str,
        name: str,
        description: Optional[str],
        pricing_model: Any,
        amount: float,
        currency: str,
        billing_interval: Optional[str],
        billing_interval_count: Optional[int],
        trial_period_days: Optional[int],
        is_active: bool,
        meta_info: Optional[dict[str, Any]] = None,
    ) -> Plan:
        plan = Plan(
            product_id=product_id,
            name=name,
            description=description,
            pricing_model=_coerce_pricing_model(pricing_model),
            amount=amount,
            currency=currency,
            billing_interval=billing_interval,
            billing_interval_count=billing_interval_count,
            trial_period_days=trial_period_days,
            is_active=is_active,
            meta_info=meta_info or {},
        )
        self.session.add(plan)
        await self.session.commit()
        await self.session.refresh(plan)
        return plan

    async def get_by_id(self, plan_id: str) -> Optional[Plan]:
        return await self.session.get(Plan, plan_id)

    async def list(
        self,
        *,
        product_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Plan]:
        stmt = select(Plan)
        if product_id:
            stmt = stmt.where(Plan.product_id == product_id)

        stmt = stmt.order_by(Plan.created_at.desc())
        if offset:
            stmt = stmt.offset(offset)
        if limit:
            stmt = stmt.limit(limit)

        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_for_product(self, product_id: str, *, limit: int = 50, offset: int = 0) -> list[Plan]:
        return await self.list(product_id=product_id, limit=limit, offset=offset)

    async def update(self, plan_id: str, **fields: Any) -> Optional[Plan]:
        plan = await self.get_by_id(plan_id)
        if not plan:
            return None
        for attr, value in fields.items():
            if hasattr(plan, attr):
                setattr(plan, attr, value)
        self.session.add(plan)
        await self.session.commit()
        await self.session.refresh(plan)
        return plan
