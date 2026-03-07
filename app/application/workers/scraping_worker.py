from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

import googlemaps
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.models.business import Business
from app.domain.models.scraping_job import ScrapingJob
from app.infrastructure.repositories.business_repository import BusinessRepository
from app.infrastructure.repositories.scraping_job_repository import ScrapingJobRepository

logger = logging.getLogger(__name__)

_MAX_PAGES = 3


class ScrapingWorker:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        google_maps_api_key: str,
    ) -> None:
        self._session_factory = session_factory
        self._api_key = google_maps_api_key

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def run_by_id(self, job_id: str) -> None:
        """Entry point for BackgroundTask. Fetches the job by ID, then runs."""
        async with self._session_factory() as session:
            job_repo = ScrapingJobRepository(session)
            job = await job_repo.find_by_id(job_id)

        if job is None:
            logger.error("ScrapingWorker: job_id=%s not found", job_id)
            return

        await self.run(job)

    async def run(self, job: ScrapingJob) -> None:
        """
        Full lifecycle:
          1. Mark job as running
          2. Fetch businesses from Google Maps
          3. Persist businesses to DB
          4. Mark job as completed / failed
        Never re-raises — all exceptions are absorbed and recorded on the job.
        """
        await self._mark_running(job)

        try:
            businesses = await self._fetch_businesses(job)

            async with self._session_factory() as session:
                biz_repo = BusinessRepository(session)
                await biz_repo.save_many(businesses)

            job.status = "completed"
            job.records_scraped = len(businesses)
            job.finished_at = datetime.now(UTC)
            async with self._session_factory() as session:
                job_repo = ScrapingJobRepository(session)
                await job_repo.update(job)

            logger.info("ScrapingWorker completed job_id=%s records=%d", job.id, len(businesses))

        except Exception as exc:
            logger.exception("ScrapingWorker failed job_id=%s", job.id)
            job.status = "failed"
            job.error_message = str(exc)
            job.finished_at = datetime.now(UTC)
            async with self._session_factory() as session:
                job_repo = ScrapingJobRepository(session)
                await job_repo.update(job)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _mark_running(self, job: ScrapingJob) -> None:
        job.status = "running"
        job.started_at = datetime.now(UTC)
        async with self._session_factory() as session:
            job_repo = ScrapingJobRepository(session)
            await job_repo.update(job)

    async def _fetch_businesses(self, job: ScrapingJob) -> list[Business]:
        """Call Google Maps Places API (Text Search + Place Details) and return domain objects."""
        gmaps: googlemaps.Client = googlemaps.Client(key=self._api_key)
        query = f"{job.category} in {job.zone}"

        raw_results: list[dict[str, object]] = []
        response: dict[str, object] = await asyncio.to_thread(gmaps.places, query=query)
        results = response.get("results")
        if isinstance(results, list):
            raw_results.extend(results)

        for _ in range(_MAX_PAGES - 1):
            next_page_token = response.get("next_page_token")
            if not next_page_token:
                break
            await asyncio.sleep(2)  # Google requires a delay before token is valid
            response = await asyncio.to_thread(
                gmaps.places, query=query, page_token=next_page_token
            )
            results = response.get("results")
            if isinstance(results, list):
                raw_results.extend(results)

        scraped_at = datetime.now(UTC)
        businesses: list[Business] = []

        for raw in raw_results:
            place_id = raw.get("place_id")
            if not isinstance(place_id, str) or not place_id:
                continue

            detail_response: dict[str, object] = await asyncio.to_thread(
                gmaps.place,
                place_id=place_id,
                fields=[
                    "name",
                    "formatted_address",
                    "formatted_phone_number",
                    "website",
                    "rating",
                    "user_ratings_total",
                    "geometry",
                    "url",
                ],
            )
            detail = detail_response.get("result")
            if not isinstance(detail, dict):
                continue

            business = self._map_to_domain(detail, job, scraped_at)
            if business is not None:
                businesses.append(business)

        return businesses

    def _map_to_domain(
        self,
        detail: dict[str, object],
        job: ScrapingJob,
        scraped_at: datetime,
    ) -> Business | None:
        name = str(detail.get("name", "")).strip()
        if not name:
            return None

        geometry = detail.get("geometry")
        lat: object = None
        lng: object = None
        if isinstance(geometry, dict):
            location = geometry.get("location")
            if isinstance(location, dict):
                lat = location.get("lat")
                lng = location.get("lng")

        def _to_decimal(value: object) -> Decimal | None:
            try:
                return Decimal(str(value)) if value is not None else None
            except InvalidOperation:
                return None

        def _to_str_or_none(value: object) -> str | None:
            s = str(value) if value is not None else ""
            return s or None

        return Business(
            id=str(uuid.uuid4()),
            scraping_job_id=job.id,
            name=name,
            category=job.category,
            zone=job.zone,
            address=_to_str_or_none(detail.get("formatted_address")),
            phone=_to_str_or_none(detail.get("formatted_phone_number")),
            website=_to_str_or_none(detail.get("website")),
            google_maps_url=_to_str_or_none(detail.get("url")),
            rating=_to_decimal(detail.get("rating")),
            review_count=int(str(detail.get("user_ratings_total") or 0)),
            latitude=_to_decimal(lat),
            longitude=_to_decimal(lng),
            is_verified=False,
            scraped_at=scraped_at,
            created_at=scraped_at,
        )
