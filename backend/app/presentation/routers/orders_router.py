from fastapi import APIRouter, Depends

from app.domain.models.current_user import CurrentUser
from app.infrastructure.dependencies import get_current_user

router = APIRouter()


@router.post("", status_code=501)
async def create_order(
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, str]:
    return {"status": "not implemented"}


@router.get("", status_code=501)
async def list_orders(
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, str]:
    return {"status": "not implemented"}


@router.get("/{order_id}", status_code=501)
async def get_order(
    order_id: str,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, str]:
    return {"status": "not implemented"}


@router.get("/{order_id}/items/{item_id}/download", status_code=501)
async def download_dataset(
    order_id: str,
    item_id: str,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, str]:
    return {"status": "not implemented"}
