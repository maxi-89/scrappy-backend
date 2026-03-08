from fastapi import APIRouter, Depends
from fastapi.responses import Response

from app.application.services.order_service import OrderService
from app.domain.models.current_user import CurrentUser
from app.infrastructure.dependencies import get_current_user, get_order_service
from app.presentation.schemas.order_schemas import (
    CreateOrderRequest,
    CreateOrderResponse,
    OrderDetailResponse,
    OrderResponse,
)

_CONTENT_TYPES: dict[str, str] = {
    "csv": "text/csv",
    "excel": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "json": "application/json",
}

router = APIRouter()


@router.post("", response_model=CreateOrderResponse, status_code=201)
async def create_order(
    payload: CreateOrderRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: OrderService = Depends(get_order_service),
) -> CreateOrderResponse:
    return await service.create_order(current_user.user_id, payload)


@router.get("", response_model=list[OrderResponse])
async def list_orders(
    current_user: CurrentUser = Depends(get_current_user),
    service: OrderService = Depends(get_order_service),
) -> list[OrderResponse]:
    return await service.list_orders(current_user.user_id)


@router.get("/{order_id}", response_model=OrderDetailResponse)
async def get_order(
    order_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    service: OrderService = Depends(get_order_service),
) -> OrderDetailResponse:
    return await service.get_order(order_id, current_user.user_id)


@router.get("/{order_id}/download")
async def download_order(
    order_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    service: OrderService = Depends(get_order_service),
) -> Response:
    data, fmt = await service.download_order(order_id, current_user.user_id)
    content_type = _CONTENT_TYPES.get(fmt, "application/octet-stream")
    return Response(content=data, media_type=content_type)
