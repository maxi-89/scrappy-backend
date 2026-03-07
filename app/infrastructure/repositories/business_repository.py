from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.business import Business
from app.domain.repositories.i_business_repository import IBusinessRepository
from app.infrastructure.database.orm_models import BusinessORM


class BusinessRepository(IBusinessRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save_many(self, businesses: list[Business]) -> None:
        orm_objects = [self._map_to_orm(b) for b in businesses]
        self._session.add_all(orm_objects)
        await self._session.commit()

    async def find_by_job_id(self, scraping_job_id: str) -> list[Business]:
        result = await self._session.execute(
            select(BusinessORM).where(BusinessORM.scraping_job_id == scraping_job_id)
        )
        return [self._map_to_domain(row) for row in result.scalars().all()]

    def _map_to_orm(self, b: Business) -> BusinessORM:
        return BusinessORM(
            id=b.id,
            scraping_job_id=b.scraping_job_id,
            name=b.name,
            category=b.category,
            zone=b.zone,
            address=b.address,
            phone=b.phone,
            website=b.website,
            google_maps_url=b.google_maps_url,
            rating=b.rating,
            review_count=b.review_count,
            latitude=b.latitude,
            longitude=b.longitude,
            is_verified=b.is_verified,
            scraped_at=b.scraped_at,
        )

    def _map_to_domain(self, row: BusinessORM) -> Business:
        return Business(
            id=row.id,
            scraping_job_id=row.scraping_job_id,
            name=row.name,
            category=row.category,
            zone=row.zone,
            address=row.address,
            phone=row.phone,
            website=row.website,
            google_maps_url=row.google_maps_url,
            rating=row.rating,
            review_count=row.review_count,
            latitude=row.latitude,
            longitude=row.longitude,
            is_verified=row.is_verified,
            scraped_at=row.scraped_at,
            created_at=row.created_at,
        )
