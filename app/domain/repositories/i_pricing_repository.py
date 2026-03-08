from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.models.pricing import Pricing


class IPricingRepository(ABC):
    @abstractmethod
    async def find_by_zone(self, zone: str) -> Pricing | None: ...

    @abstractmethod
    async def find_all(self) -> list[Pricing]: ...

    @abstractmethod
    async def upsert(self, zone: str, price_usd: str) -> Pricing: ...
