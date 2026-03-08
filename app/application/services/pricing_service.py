from __future__ import annotations

from app.domain.repositories.i_pricing_repository import IPricingRepository
from app.presentation.schemas.pricing_schemas import PricingEntryResponse, UpsertPricingRequest


class PricingService:
    def __init__(self, repository: IPricingRepository) -> None:
        self._repository = repository

    async def list_pricing(self) -> list[PricingEntryResponse]:
        entries = await self._repository.find_all()
        return [
            PricingEntryResponse(id=p.id, zone=p.zone, price_usd=float(p.price_usd))
            for p in entries
        ]

    async def upsert_pricing(self, payload: UpsertPricingRequest) -> list[PricingEntryResponse]:
        results = []
        for entry in payload.entries:
            pricing = await self._repository.upsert(entry.zone, str(entry.price_usd))
            results.append(
                PricingEntryResponse(id=pricing.id, zone=pricing.zone, price_usd=float(pricing.price_usd))
            )
        return results
