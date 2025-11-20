"""Payment repository."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Payment, PaymentStatus


def _normalize_status(status: Optional[str]) -> PaymentStatus:
    if isinstance(status, PaymentStatus):
        return status
    if not status:
        return PaymentStatus.PENDING
    normalized = status.lower()
    mapping = {
        "succeeded": PaymentStatus.COMPLETED,
        "completed": PaymentStatus.COMPLETED,
        "processing": PaymentStatus.PROCESSING,
        "pending": PaymentStatus.PENDING,
        "failed": PaymentStatus.FAILED,
        "refunded": PaymentStatus.REFUNDED,
        "partially_refunded": PaymentStatus.PARTIALLY_REFUNDED,
        "canceled": PaymentStatus.CANCELED,
        "cancelled": PaymentStatus.CANCELED,
        "expired": PaymentStatus.EXPIRED,
    }
    return mapping.get(normalized, PaymentStatus.PENDING)


class PaymentRepository:
    """Repository for payment persistence."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        customer_id: str,
        provider: str,
        provider_payment_id: str,
        amount: float,
        currency: str,
        status: Any,
        payment_method: Optional[str] = None,
        error_message: Optional[str] = None,
        meta_info: Optional[dict[str, Any]] = None,
    ) -> Payment:
        payment = Payment(
            customer_id=customer_id,
            provider=provider,
            provider_payment_id=provider_payment_id,
            amount=amount,
            currency=currency,
            status=_normalize_status(status),
            payment_method=payment_method,
            error_message=error_message,
            meta_info=meta_info or {},
        )
        self.session.add(payment)
        await self.session.commit()
        await self.session.refresh(payment)
        return payment

    async def get_by_id(self, payment_id: str) -> Optional[Payment]:
        return await self.session.get(Payment, payment_id)

    async def update(self, payment_id: str, **fields: Any) -> Optional[Payment]:
        payment = await self.get_by_id(payment_id)
        if not payment:
            return None

        if "status" in fields:
            fields["status"] = _normalize_status(fields["status"])

        for attr, value in fields.items():
            if hasattr(payment, attr):
                setattr(payment, attr, value)

        self.session.add(payment)
        await self.session.commit()
        await self.session.refresh(payment)
        return payment

    async def list(
        self,
        *,
        customer_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        include_customer: bool = True,
    ) -> list[Payment]:
        stmt = select(Payment)
        if include_customer:
            stmt = stmt.options(joinedload(Payment.customer))

        if customer_id:
            stmt = stmt.where(Payment.customer_id == customer_id)
        if status:
            stmt = stmt.where(Payment.status == _normalize_status(status))

        stmt = stmt.order_by(Payment.created_at.desc())
        if offset:
            stmt = stmt.offset(offset)
        if limit:
            stmt = stmt.limit(limit)

        result = await self.session.execute(stmt)
        return result.scalars().all()
