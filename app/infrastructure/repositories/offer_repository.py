from __future__ import annotations

from sqlalchemy import select
from sqlalchemy import update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.offer import Offer
from app.domain.repositories.i_offer_repository import IOfferRepository
from app.infrastructure.database.orm_models import OfferORM, OrderORM


class OfferRepository(IOfferRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, offer: Offer) -> None:
        orm = OfferORM(
            id=offer.id,
            title=offer.title,
            category=offer.category,
            description=offer.description,
            is_active=offer.is_active,
            created_at=offer.created_at,
            updated_at=offer.updated_at,
        )
        self._session.add(orm)
        await self._session.commit()

    async def find_by_id(self, offer_id: str) -> Offer | None:
        result = await self._session.execute(
            select(OfferORM).where(OfferORM.id == offer_id)
        )
        row = result.scalar_one_or_none()
        return self._map_to_domain(row) if row else None

    async def find_by_category(self, category: str) -> Offer | None:
        result = await self._session.execute(
            select(OfferORM).where(OfferORM.category == category)
        )
        row = result.scalar_one_or_none()
        return self._map_to_domain(row) if row else None

    async def find_all(self) -> list[Offer]:
        result = await self._session.execute(select(OfferORM))
        return [self._map_to_domain(row) for row in result.scalars().all()]

    async def update(self, offer: Offer) -> None:
        stmt = (
            sa_update(OfferORM)
            .where(OfferORM.id == offer.id)
            .values(
                title=offer.title,
                description=offer.description,
                is_active=offer.is_active,
                updated_at=offer.updated_at,
            )
        )
        await self._session.execute(stmt)
        await self._session.commit()

    async def delete(self, offer_id: str) -> None:
        result = await self._session.execute(
            select(OfferORM).where(OfferORM.id == offer_id)
        )
        row = result.scalar_one_or_none()
        if row:
            await self._session.delete(row)
            await self._session.commit()

    async def has_orders(self, offer_id: str) -> bool:
        result = await self._session.execute(
            select(OrderORM.id).where(OrderORM.offer_id == offer_id).limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def find_all_active(self) -> list[Offer]:
        result = await self._session.execute(
            select(OfferORM).where(OfferORM.is_active == True)  # noqa: E712
        )
        return [self._map_to_domain(row) for row in result.scalars().all()]

    async def find_active_by_id(self, offer_id: str) -> Offer | None:
        result = await self._session.execute(
            select(OfferORM).where(OfferORM.id == offer_id, OfferORM.is_active == True)  # noqa: E712
        )
        row = result.scalar_one_or_none()
        return self._map_to_domain(row) if row else None

    def _map_to_domain(self, row: OfferORM) -> Offer:
        return Offer(
            id=row.id,
            title=row.title,
            category=row.category,
            description=row.description,
            is_active=row.is_active,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
