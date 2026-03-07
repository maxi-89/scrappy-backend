"""Lambda entry point for Step Functions SaveBusinesses state.

Input:  {"job_id": "<uuid>", "businesses": [<serialized Business dicts>]}
Output: {"job_id": "<uuid>", "records_saved": <int>}
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.domain.models.business import Business
from app.infrastructure.database.session import AsyncSessionLocal
from app.infrastructure.repositories.business_repository import BusinessRepository
from app.infrastructure.repositories.scraping_job_repository import ScrapingJobRepository

logger = logging.getLogger(__name__)


def _dict_to_business(data: dict[str, Any]) -> Business:
    """Deserialize a JSON dict (Decimal as str, datetime as ISO str) back to a Business."""

    def _decimal(v: Any) -> Decimal | None:
        return Decimal(v) if v is not None else None

    def _dt(v: Any) -> datetime:
        return datetime.fromisoformat(v)

    return Business(
        id=data["id"],
        scraping_job_id=data["scraping_job_id"],
        name=data["name"],
        category=data["category"],
        zone=data["zone"],
        address=data.get("address"),
        phone=data.get("phone"),
        website=data.get("website"),
        google_maps_url=data.get("google_maps_url"),
        rating=_decimal(data.get("rating")),
        review_count=int(data.get("review_count", 0)),
        latitude=_decimal(data.get("latitude")),
        longitude=_decimal(data.get("longitude")),
        is_verified=bool(data.get("is_verified", False)),
        scraped_at=_dt(data["scraped_at"]),
        created_at=_dt(data["created_at"]),
    )


async def _run(event: dict[str, Any]) -> dict[str, Any]:
    job_id: str = event["job_id"]
    raw_businesses: list[dict[str, Any]] = event.get("businesses", [])

    businesses = [_dict_to_business(b) for b in raw_businesses]

    async with AsyncSessionLocal() as session:
        biz_repo = BusinessRepository(session)
        await biz_repo.save_many(businesses)

    async with AsyncSessionLocal() as session:
        job_repo = ScrapingJobRepository(session)
        job = await job_repo.find_by_id(job_id)

    if job is None:
        raise ValueError(f"ScrapingJob not found: {job_id}")

    job.status = "completed"
    job.records_scraped = len(businesses)
    job.finished_at = datetime.now(UTC)

    async with AsyncSessionLocal() as session:
        job_repo = ScrapingJobRepository(session)
        await job_repo.update(job)

    logger.info("SaveBusinesses completed job_id=%s records=%d", job_id, len(businesses))
    return {"job_id": job_id, "records_saved": len(businesses)}


def handler(event: dict[str, Any], context: object) -> dict[str, Any]:
    return asyncio.run(_run(event))
