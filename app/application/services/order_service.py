from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.domain.models.order import Order
from app.domain.models.scraping_job import ScrapingJob
from app.domain.repositories.i_offer_repository import IOfferRepository
from app.domain.repositories.i_order_repository import IOrderRepository
from app.domain.repositories.i_pricing_repository import IPricingRepository
from app.domain.repositories.i_scraping_job_repository import IScrapingJobRepository
from app.infrastructure.errors.app_error import AppError
from app.infrastructure.stripe.stripe_client import IStripeClient
from app.presentation.schemas.order_schemas import (
    CreateOrderRequest,
    CreateOrderResponse,
    OrderDetailResponse,
    OrderResponse,
    ScrapingJobSchema,
)


class OrderService:
    def __init__(
        self,
        order_repository: IOrderRepository,
        offer_repository: IOfferRepository,
        pricing_repository: IPricingRepository,
        stripe_client: IStripeClient,
        scraping_job_repository: IScrapingJobRepository | None = None,
    ) -> None:
        self._order_repository = order_repository
        self._offer_repository = offer_repository
        self._pricing_repository = pricing_repository
        self._stripe_client = stripe_client
        self._scraping_job_repository = scraping_job_repository

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

    async def list_orders(self, user_id: str) -> list[OrderResponse]:
        orders = await self._order_repository.find_by_user(user_id)
        return [self._to_order_response(o) for o in orders]

    async def get_order(self, order_id: str, user_id: str) -> OrderDetailResponse:
        order = await self._order_repository.find_by_id(order_id)
        if order is None:
            raise AppError("Order not found", status_code=404)
        if order.user_id != user_id:
            raise AppError("Access denied", status_code=403)

        scraping_job: ScrapingJob | None = None
        if order.scraping_job_id and self._scraping_job_repository:
            scraping_job = await self._scraping_job_repository.find_by_id(order.scraping_job_id)

        return OrderDetailResponse(
            id=order.id,
            offer_id=order.offer_id,
            zone=order.zone,
            format=order.format,
            status=order.status,
            total_usd=float(order.total_usd),
            created_at=order.created_at,
            paid_at=order.paid_at,
            completed_at=order.completed_at,
            scraping_job=self._to_scraping_job_schema(scraping_job) if scraping_job else None,
        )

    @staticmethod
    def _to_order_response(order: Order) -> OrderResponse:
        return OrderResponse(
            id=order.id,
            offer_id=order.offer_id,
            zone=order.zone,
            format=order.format,
            status=order.status,
            total_usd=float(order.total_usd),
            created_at=order.created_at,
            paid_at=order.paid_at,
            completed_at=order.completed_at,
        )

    @staticmethod
    def _to_scraping_job_schema(job: ScrapingJob) -> ScrapingJobSchema:
        return ScrapingJobSchema(
            id=job.id,
            category=job.category,
            zone=job.zone,
            status=job.status,
            records_scraped=job.records_scraped,
            error_message=job.error_message,
            started_at=job.started_at,
            finished_at=job.finished_at,
            created_at=job.created_at,
        )
