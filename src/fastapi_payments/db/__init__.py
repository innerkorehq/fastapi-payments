"""Database convenience helpers for FastAPI Payments."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine

from .repositories import initialize_db as _initialize_db
from .models import Base


async def init_engine_and_schema(engine: AsyncEngine) -> None:
	"""Create database schema if it does not exist."""
	async with engine.begin() as conn:
		await conn.run_sync(Base.metadata.create_all)


def setup_database(config) -> AsyncEngine:
	"""Initialize engine and ensure schema is present."""
	engine = _initialize_db(config)
	return engine
