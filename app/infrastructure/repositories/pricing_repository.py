from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.pricing import Pricing
from app.domain.repositories.i_pricing_repository import IPricingRepository
from app.infrastructure.database.orm_models import PricingORM


class PricingRepository(IPricingRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_zone(self, zone: str) -> Pricing | None:
        result = await self._session.execute(
            select(PricingORM).where(PricingORM.zone == zone)
        )
        row = result.scalar_one_or_none()
        return self._map_to_domain(row) if row else None

    async def find_all(self) -> list[Pricing]:
        result = await self._session.execute(select(PricingORM).order_by(PricingORM.zone))
        return [self._map_to_domain(row) for row in result.scalars().all()]

    async def upsert(self, zone: str, price_usd: str) -> Pricing:
        result = await self._session.execute(
            select(PricingORM).where(PricingORM.zone == zone)
        )
        row = result.scalar_one_or_none()
        now = datetime.now(UTC)
        if row is None:
            row = PricingORM(
                id=str(uuid.uuid4()),
                zone=zone,
                price_usd=Decimal(price_usd),
                created_at=now,
                updated_at=now,
            )
            self._session.add(row)
        else:
            row.price_usd = Decimal(price_usd)
            row.updated_at = now
        await self._session.commit()
        return self._map_to_domain(row)

    def _map_to_domain(self, row: PricingORM) -> Pricing:
        return Pricing(
            id=row.id,
            zone=row.zone,
            price_usd=Decimal(str(row.price_usd)),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
