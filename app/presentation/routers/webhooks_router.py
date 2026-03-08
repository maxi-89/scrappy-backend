import logging

from fastapi import APIRouter, Header, Request

from app.application.services.webhook_service import StripeWebhookService
from app.infrastructure.dependencies import get_webhook_service
from app.infrastructure.errors.app_error import AppError
from fastapi import Depends

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(default=None, alias="stripe-signature"),
    service: StripeWebhookService = Depends(get_webhook_service),
) -> dict[str, str]:
    if stripe_signature is None:
        raise AppError("Missing Stripe-Signature header", status_code=400)
    payload = await request.body()
    await service.handle_event(payload, stripe_signature)
    return {"status": "ok"}
