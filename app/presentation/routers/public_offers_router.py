from fastapi import APIRouter, Depends

from app.application.services.offer_service import OfferService
from app.infrastructure.dependencies import get_offer_service
from app.infrastructure.errors.app_error import AppError
from app.presentation.schemas.offer_schemas import PublicOfferResponse

router = APIRouter()


@router.get("", response_model=list[PublicOfferResponse])
async def list_offers(
    zone: str | None = None,
    service: OfferService = Depends(get_offer_service),
) -> list[PublicOfferResponse]:
    return await service.list_active_offers(zone=zone)


@router.get("/{offer_id}", response_model=PublicOfferResponse)
async def get_offer(
    offer_id: str,
    zone: str | None = None,
    service: OfferService = Depends(get_offer_service),
) -> PublicOfferResponse:
    offer = await service.get_active_offer(offer_id, zone=zone)
    if offer is None:
        raise AppError("Offer not found", status_code=404)
    return offer
