from fastapi import APIRouter, Depends

from app.application.services.offer_service import OfferService
from app.infrastructure.dependencies import get_admin_key, get_offer_service
from app.infrastructure.errors.app_error import AppError
from app.presentation.schemas.offer_schemas import (
    CreateOfferRequest,
    OfferResponse,
    UpdateOfferRequest,
)

router = APIRouter()


@router.post("", response_model=OfferResponse, status_code=201)
async def create_offer(
    payload: CreateOfferRequest,
    _: str = Depends(get_admin_key),
    service: OfferService = Depends(get_offer_service),
) -> OfferResponse:
    return await service.create_offer(payload)


@router.patch("/{offer_id}", response_model=OfferResponse)
async def update_offer(
    offer_id: str,
    payload: UpdateOfferRequest,
    _: str = Depends(get_admin_key),
    service: OfferService = Depends(get_offer_service),
) -> OfferResponse:
    offer = await service.update_offer(offer_id, payload)
    if offer is None:
        raise AppError("Offer not found", status_code=404)
    return offer


@router.delete("/{offer_id}", status_code=204)
async def delete_offer(
    offer_id: str,
    _: str = Depends(get_admin_key),
    service: OfferService = Depends(get_offer_service),
) -> None:
    await service.delete_offer(offer_id)
