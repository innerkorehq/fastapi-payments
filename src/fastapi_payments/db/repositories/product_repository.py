"""Product repository."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Product


class ProductRepository:
    """Repository for product CRUD operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        name: str,
        description: Optional[str] = None,
        meta_info: Optional[dict[str, Any]] = None,
    ) -> Product:
        product = Product(name=name, description=description, meta_info=meta_info or {})
        self.session.add(product)
        await self.session.commit()
        await self.session.refresh(product)
        return product

    async def get_by_id(self, product_id: str) -> Optional[Product]:
        return await self.session.get(Product, product_id)

    async def list(self, *, limit: int = 50, offset: int = 0) -> list[Product]:
        stmt = select(Product).order_by(Product.created_at.desc())
        if offset:
            stmt = stmt.offset(offset)
        if limit:
            stmt = stmt.limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def update(self, product_id: str, **fields: Any) -> Optional[Product]:
        product = await self.get_by_id(product_id)
        if not product:
            return None
        for attr, value in fields.items():
            if hasattr(product, attr):
                setattr(product, attr, value)
        self.session.add(product)
        await self.session.commit()
        await self.session.refresh(product)
        return product
