from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.models.offer import Offer


class IOfferRepository(ABC):
    @abstractmethod
    async def save(self, offer: Offer) -> None: ...

    @abstractmethod
    async def find_by_id(self, offer_id: str) -> Offer | None: ...

    @abstractmethod
    async def find_by_category(self, category: str) -> Offer | None: ...

    @abstractmethod
    async def find_all(self) -> list[Offer]: ...

    @abstractmethod
    async def update(self, offer: Offer) -> None: ...

    @abstractmethod
    async def delete(self, offer_id: str) -> None: ...

    @abstractmethod
    async def has_orders(self, offer_id: str) -> bool:
        """Return True if the offer has any associated orders."""
        ...

    @abstractmethod
    async def find_all_active(self) -> list[Offer]: ...

    @abstractmethod
    async def find_active_by_id(self, offer_id: str) -> Offer | None: ...
