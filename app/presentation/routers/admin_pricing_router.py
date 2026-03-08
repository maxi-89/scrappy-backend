from fastapi import APIRouter, Depends

from app.application.services.pricing_service import PricingService
from app.infrastructure.dependencies import get_admin_key, get_pricing_service
from app.presentation.schemas.pricing_schemas import PricingEntryResponse, UpsertPricingRequest

router = APIRouter()


@router.get("", response_model=list[PricingEntryResponse])
async def list_pricing(
    _: str = Depends(get_admin_key),
    service: PricingService = Depends(get_pricing_service),
) -> list[PricingEntryResponse]:
    return await service.list_pricing()


@router.put("", response_model=list[PricingEntryResponse])
async def upsert_pricing(
    payload: UpsertPricingRequest,
    _: str = Depends(get_admin_key),
    service: PricingService = Depends(get_pricing_service),
) -> list[PricingEntryResponse]:
    return await service.upsert_pricing(payload)
