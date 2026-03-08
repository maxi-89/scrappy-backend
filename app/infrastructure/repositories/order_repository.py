from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy import update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.order import Order
from app.domain.repositories.i_order_repository import IOrderRepository
from app.infrastructure.database.orm_models import OrderORM


class OrderRepository(IOrderRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, order: Order) -> None:
        orm = OrderORM(
            id=order.id,
            user_id=order.user_id,
            offer_id=order.offer_id,
            zone=order.zone,
            format=order.format,
            status=order.status,
            total_usd=order.total_usd,
            stripe_payment_intent_id=order.stripe_payment_intent_id,
            scraping_job_id=order.scraping_job_id,
            result_path=order.result_path,
            created_at=order.created_at,
            paid_at=order.paid_at,
            completed_at=order.completed_at,
        )
        self._session.add(orm)
        await self._session.commit()

    async def find_by_id(self, order_id: str) -> Order | None:
        result = await self._session.execute(
            select(OrderORM).where(OrderORM.id == order_id)
        )
        row = result.scalar_one_or_none()
        return self._map_to_domain(row) if row else None

    async def find_by_user(self, user_id: str) -> list[Order]:
        result = await self._session.execute(
            select(OrderORM).where(OrderORM.user_id == user_id)
        )
        return [self._map_to_domain(row) for row in result.scalars().all()]

    async def update(self, order: Order) -> None:
        stmt = (
            sa_update(OrderORM)
            .where(OrderORM.id == order.id)
            .values(
                status=order.status,
                scraping_job_id=order.scraping_job_id,
                result_path=order.result_path,
                paid_at=order.paid_at,
                completed_at=order.completed_at,
            )
        )
        await self._session.execute(stmt)
        await self._session.commit()

    def _map_to_domain(self, row: OrderORM) -> Order:
        return Order(
            id=row.id,
            user_id=row.user_id,
            offer_id=row.offer_id,
            zone=row.zone,
            format=row.format,
            status=row.status,
            total_usd=Decimal(str(row.total_usd)),
            stripe_payment_intent_id=row.stripe_payment_intent_id,
            scraping_job_id=row.scraping_job_id,
            result_path=row.result_path,
            created_at=row.created_at,
            paid_at=row.paid_at,
            completed_at=row.completed_at,
        )
