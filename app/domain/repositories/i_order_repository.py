from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.models.order import Order


class IOrderRepository(ABC):
    @abstractmethod
    async def save(self, order: Order) -> None: ...

    @abstractmethod
    async def find_by_id(self, order_id: str) -> Order | None: ...

    @abstractmethod
    async def find_by_user(self, user_id: str) -> list[Order]: ...

    @abstractmethod
    async def update(self, order: Order) -> None: ...

    @abstractmethod
    async def find_by_stripe_payment_intent_id(self, payment_intent_id: str) -> Order | None: ...
