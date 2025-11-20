"""Generic repository helpers for SQLAlchemy models."""

from __future__ import annotations

from typing import Any, Dict, Generic, List, Optional, Type, TypeVar

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

ModelType = TypeVar("ModelType")


class BaseRepository(Generic[ModelType]):
    """Lightweight repository that performs basic CRUD operations."""

    def __init__(self, model: Type[ModelType], session: AsyncSession):
        self._model = model
        self._session = session

    async def create(self, **kwargs: Any) -> ModelType:
        instance = self._model(**kwargs)
        self._session.add(instance)
        await self._session.commit()
        await self._session.refresh(instance)
        return instance

    async def get_by_id(self, obj_id: Any) -> Optional[ModelType]:
        return await self._session.get(self._model, obj_id)

    async def list(self, **filters: Any) -> List[ModelType]:
        stmt = select(self._model)
        for field, value in filters.items():
            stmt = stmt.where(getattr(self._model, field) == value)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def update(self, obj_id: Any, **kwargs: Any) -> Optional[ModelType]:
        instance = await self.get_by_id(obj_id)
        if not instance:
            return None
        for field, value in kwargs.items():
            setattr(instance, field, value)
        self._session.add(instance)
        await self._session.commit()
        await self._session.refresh(instance)
        return instance

    async def delete(self, obj_id: Any) -> None:
        instance = await self.get_by_id(obj_id)
        if not instance:
            return
        await self._session.delete(instance)
        await self._session.commit()

    async def delete_where(self, **filters: Any) -> None:
        stmt = delete(self._model)
        for field, value in filters.items():
            stmt = stmt.where(getattr(self._model, field) == value)
        await self._session.execute(stmt)
        await self._session.commit()
