from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.models.scraping_job import ScrapingJob


class IScrapingJobRepository(ABC):
    @abstractmethod
    async def save(self, job: ScrapingJob) -> None: ...

    @abstractmethod
    async def find_by_id(self, job_id: str) -> ScrapingJob | None: ...

    @abstractmethod
    async def find_all(self, status: str | None = None) -> list[ScrapingJob]: ...
