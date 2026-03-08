from fastapi import APIRouter, Depends

from app.application.services.order_service import OrderService
from app.infrastructure.dependencies import get_admin_key, get_order_service
from app.presentation.schemas.order_schemas import OrderDetailResponse

router = APIRouter()


@router.get("", response_model=list[OrderDetailResponse])
async def list_all_orders(
    status: str | None = None,
    _: str = Depends(get_admin_key),
    service: OrderService = Depends(get_order_service),
) -> list[OrderDetailResponse]:
    return await service.list_all_orders_detailed(status)
