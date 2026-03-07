from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.domain.models.offer import Offer
from app.domain.repositories.i_offer_repository import IOfferRepository
from app.infrastructure.errors.app_error import AppError
from app.presentation.schemas.offer_schemas import (
    CreateOfferRequest,
    OfferResponse,
    UpdateOfferRequest,
)


class OfferService:
    def __init__(self, repository: IOfferRepository) -> None:
        self._repository = repository

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
