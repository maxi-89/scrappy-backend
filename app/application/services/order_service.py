from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.domain.models.order import Order
from app.domain.repositories.i_offer_repository import IOfferRepository
from app.domain.repositories.i_order_repository import IOrderRepository
from app.domain.repositories.i_pricing_repository import IPricingRepository
from app.infrastructure.errors.app_error import AppError
from app.infrastructure.stripe.stripe_client import IStripeClient
from app.presentation.schemas.order_schemas import CreateOrderRequest, CreateOrderResponse


class OrderService:
    def __init__(
        self,
        order_repository: IOrderRepository,
        offer_repository: IOfferRepository,
        pricing_repository: IPricingRepository,
        stripe_client: IStripeClient,
    ) -> None:
        self._order_repository = order_repository
        self._offer_repository = offer_repository
        self._pricing_repository = pricing_repository
        self._stripe_client = stripe_client

    async def create_order(self, user_id: str, payload: CreateOrderRequest) -> CreateOrderResponse:
        offer = await self._offer_repository.find_active_by_id(payload.offer_id)
        if offer is None:
            raise AppError("Offer not found", status_code=404)

        pricing = await self._pricing_repository.find_by_zone(payload.zone)
        if pricing is None:
            raise AppError(f"No pricing configured for zone '{payload.zone}'", status_code=404)

        order_id = str(uuid.uuid4())
        payment = self._stripe_client.create_payment_intent(
            amount_usd=float(pricing.price_usd),
            order_id=order_id,
        )

        now = datetime.now(UTC)
        order = Order(
            id=order_id,
            user_id=user_id,
            offer_id=payload.offer_id,
            zone=payload.zone,
            format=payload.format,
            status="pending",
            total_usd=pricing.price_usd,
            stripe_payment_intent_id=payment.payment_intent_id,
            scraping_job_id=None,
            result_path=None,
            created_at=now,
            paid_at=None,
            completed_at=None,
        )
        await self._order_repository.save(order)

        return CreateOrderResponse(
            order_id=order_id,
            client_secret=payment.client_secret,
            total_usd=float(pricing.price_usd),
        )
