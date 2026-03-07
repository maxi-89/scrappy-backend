from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.scraping_job import ScrapingJob
from app.domain.repositories.i_scraping_job_repository import IScrapingJobRepository
from app.infrastructure.database.orm_models import ScrapingJobORM


class ScrapingJobRepository(IScrapingJobRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, job: ScrapingJob) -> None:
        orm = ScrapingJobORM(
            id=job.id,
            order_id=job.order_id,
            category=job.category,
            zone=job.zone,
            status=job.status,
            records_scraped=job.records_scraped,
            error_message=job.error_message,
            started_at=job.started_at,
            finished_at=job.finished_at,
            created_at=job.created_at,
        )
        self._session.add(orm)
        await self._session.commit()

    async def find_by_id(self, job_id: str) -> ScrapingJob | None:
        result = await self._session.execute(
            select(ScrapingJobORM).where(ScrapingJobORM.id == job_id)
        )
        row = result.scalar_one_or_none()
        return self._map_to_domain(row) if row else None

    async def find_all(self, status: str | None = None) -> list[ScrapingJob]:
        stmt = select(ScrapingJobORM)
        if status is not None:
            stmt = stmt.where(ScrapingJobORM.status == status)
        result = await self._session.execute(stmt)
        return [self._map_to_domain(row) for row in result.scalars().all()]

    def _map_to_domain(self, row: ScrapingJobORM) -> ScrapingJob:
        return ScrapingJob(
            id=row.id,
            order_id=row.order_id,
            category=row.category,
            zone=row.zone,
            status=row.status,
            records_scraped=row.records_scraped,
            error_message=row.error_message,
            started_at=row.started_at,
            finished_at=row.finished_at,
            created_at=row.created_at,
        )
