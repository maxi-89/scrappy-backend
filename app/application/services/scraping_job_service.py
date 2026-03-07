from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.domain.models.scraping_job import ScrapingJob
from app.domain.repositories.i_scraping_job_repository import IScrapingJobRepository
from app.presentation.schemas.scraping_job_schemas import (
    CreateScrapingJobRequest,
    ScrapingJobResponse,
)


class ScrapingJobService:
    def __init__(self, repository: IScrapingJobRepository) -> None:
        self._repository = repository

    async def create_job(self, payload: CreateScrapingJobRequest) -> ScrapingJobResponse:
        job = ScrapingJob(
            id=str(uuid.uuid4()),
            category=payload.category,
            zone=payload.zone,
            status="pending",
            order_id=None,
            records_scraped=0,
            error_message=None,
            started_at=None,
            finished_at=None,
            created_at=datetime.now(UTC),
        )
        await self._repository.save(job)
        return ScrapingJobResponse.model_validate(job.__dict__)

    async def list_jobs(self, status: str | None = None) -> list[ScrapingJobResponse]:
        jobs = await self._repository.find_all(status=status)
        return [ScrapingJobResponse.model_validate(j.__dict__) for j in jobs]

    async def get_job(self, job_id: str) -> ScrapingJobResponse | None:
        job = await self._repository.find_by_id(job_id)
        if job is None:
            return None
        return ScrapingJobResponse.model_validate(job.__dict__)
