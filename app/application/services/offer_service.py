from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.domain.models.offer import Offer
from app.domain.repositories.i_offer_repository import IOfferRepository
from app.domain.repositories.i_pricing_repository import IPricingRepository
from app.infrastructure.errors.app_error import AppError
from app.presentation.schemas.offer_schemas import (
    CreateOfferRequest,
    OfferResponse,
    PublicOfferResponse,
    UpdateOfferRequest,
)


class OfferService:
    def __init__(
        self,
        repository: IOfferRepository,
        pricing_repository: IPricingRepository | None = None,
    ) -> None:
        self._repository = repository
        self._pricing_repository = pricing_repository

    async def create_offer(self, payload: CreateOfferRequest) -> OfferResponse:
        existing = await self._repository.find_by_category(payload.category)
        if existing is not None:
            raise AppError(f"Offer with category '{payload.category}' already exists", status_code=409)

        now = datetime.now(UTC)
        offer = Offer(
            id=str(uuid.uuid4()),
            title=payload.title,
            category=payload.category,
            description=payload.description,
            is_active=payload.is_active,
            created_at=now,
            updated_at=now,
        )
        await self._repository.save(offer)
        return OfferResponse.model_validate(offer.__dict__)

    async def update_offer(self, offer_id: str, payload: UpdateOfferRequest) -> OfferResponse:
        offer = await self._repository.find_by_id(offer_id)
        if offer is None:
            raise AppError("Offer not found", status_code=404)

        if payload.title is not None:
            offer.title = payload.title
        if payload.description is not None:
            offer.description = payload.description
        if payload.is_active is not None:
            offer.is_active = payload.is_active
        offer.updated_at = datetime.now(UTC)

        await self._repository.update(offer)
        return OfferResponse.model_validate(offer.__dict__)

    async def delete_offer(self, offer_id: str) -> None:
        offer = await self._repository.find_by_id(offer_id)
        if offer is None:
            raise AppError("Offer not found", status_code=404)

        if await self._repository.has_orders(offer_id):
            raise AppError("Cannot delete offer with associated orders", status_code=409)

        await self._repository.delete(offer_id)

    async def list_active_offers(self, zone: str | None) -> list[PublicOfferResponse]:
        offers = await self._repository.find_all_active()
        price_usd = await self._resolve_price(zone)
        return [
            PublicOfferResponse(
                id=o.id,
                title=o.title,
                category=o.category,
                description=o.description,
                is_active=o.is_active,
                price_usd=price_usd,
            )
            for o in offers
        ]

    async def get_active_offer(self, offer_id: str, zone: str | None) -> PublicOfferResponse | None:
        offer = await self._repository.find_active_by_id(offer_id)
        if offer is None:
            return None
        price_usd = await self._resolve_price(zone)
        return PublicOfferResponse(
            id=offer.id,
            title=offer.title,
            category=offer.category,
            description=offer.description,
            is_active=offer.is_active,
            price_usd=price_usd,
        )

    async def _resolve_price(self, zone: str | None) -> float | None:
        if zone is None or self._pricing_repository is None:
            return None
        pricing = await self._pricing_repository.find_by_zone(zone)
        return float(pricing.price_usd) if pricing else None
