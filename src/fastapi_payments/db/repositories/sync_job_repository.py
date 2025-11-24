"""SyncJob repository for background sync jobs."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import SyncJob


class SyncJobRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, resources: Optional[Any] = None, provider: Optional[str] = None, filters: Optional[Any] = None) -> SyncJob:
        job = SyncJob(resources=resources, provider=provider, filters=filters)
        self.session.add(job)
        await self.session.commit()
        await self.session.refresh(job)
        return job

    async def get_by_id(self, job_id: str) -> Optional[SyncJob]:
        return await self.session.get(SyncJob, job_id)

    async def update_status(self, job_id: str, status: str, result: Optional[Any] = None) -> Optional[SyncJob]:
        job = await self.get_by_id(job_id)
        if not job:
            return None
        job.status = status
        if result is not None:
            job.result = result
        self.session.add(job)
        await self.session.commit()
        await self.session.refresh(job)
        return job
