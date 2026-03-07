from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.models.business import Business


class IBusinessRepository(ABC):
    @abstractmethod
    async def save_many(self, businesses: list[Business]) -> None:
        """Persist a batch of business records in a single transaction."""
        ...

    @abstractmethod
    async def find_by_job_id(self, scraping_job_id: str) -> list[Business]:
        """Return all business records associated with a given scraping job."""
        ...
