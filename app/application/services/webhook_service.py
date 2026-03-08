from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

import stripe as stripe_lib

from app.domain.models.scraping_job import ScrapingJob
from app.domain.repositories.i_offer_repository import IOfferRepository
from app.domain.repositories.i_order_repository import IOrderRepository
from app.domain.repositories.i_scraping_job_repository import IScrapingJobRepository
from app.infrastructure.aws.sfn_client import SfnStarterClient
from app.infrastructure.errors.app_error import AppError
from app.infrastructure.stripe.stripe_client import IStripeClient

logger = logging.getLogger(__name__)


class StripeWebhookService:
    def __init__(
        self,
        stripe_client: IStripeClient,
        order_repository: IOrderRepository,
        offer_repository: IOfferRepository,
        scraping_job_repository: IScrapingJobRepository,
        sfn_client: SfnStarterClient,
        webhook_secret: str,
    ) -> None:
        self._stripe = stripe_client
        self._order_repo = order_repository
        self._offer_repo = offer_repository
        self._job_repo = scraping_job_repository
        self._sfn = sfn_client
        self._webhook_secret = webhook_secret

    async def handle_event(self, payload: bytes, sig_header: str) -> None:
        try:
            event: dict[str, Any] = self._stripe.construct_event(
                payload, sig_header, self._webhook_secret
            )
        except stripe_lib.error.SignatureVerificationError as exc:
            raise AppError("Invalid Stripe signature", status_code=400) from exc

        event_type: str = event.get("type", "")

        if event_type == "payment_intent.succeeded":
            await self._handle_payment_succeeded(event)
        else:
            logger.info("Ignoring unhandled Stripe event type: %s", event_type)

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    async def _handle_payment_succeeded(self, event: dict[str, Any]) -> None:
        pi_id: str = event["data"]["object"]["id"]

        order = await self._order_repo.find_by_stripe_payment_intent_id(pi_id)
        if order is None:
            logger.warning("Order not found for payment_intent_id=%s — skipping", pi_id)
            return

        if order.status != "pending":
            logger.info("Order %s already processed (status=%s) — skipping", order.id, order.status)
            return

        # Mark order as paid
        now = datetime.now(UTC)
        order.status = "paid"
        order.paid_at = now
        await self._order_repo.update(order)

        # Get offer category
        offer = await self._offer_repo.find_by_id(order.offer_id)
        if offer is None:
            logger.warning("Offer %s not found for order %s — skipping scraping", order.offer_id, order.id)
            return
        category = offer.category

        # Create scraping job
        job_id = str(uuid.uuid4())
        job = ScrapingJob(
            id=job_id,
            category=category,
            zone=order.zone,
            status="pending",
            order_id=order.id,
            records_scraped=0,
            error_message=None,
            started_at=None,
            finished_at=None,
            created_at=now,
        )
        await self._job_repo.save(job)

        # Link scraping job to order
        order.scraping_job_id = job_id
        await self._order_repo.update(order)

        # Trigger SFN async
        await asyncio.to_thread(self._sfn.start_execution, job_id)

        logger.info("Order %s paid — scraping job %s triggered", order.id, job_id)
