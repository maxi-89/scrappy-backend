"""Lambda entry point for Step Functions ScrapeBusinesses state.

Input:  {"job_id": "<uuid>", "category": "<str>", "zone": "<str>"}
Output: {"job_id": "<uuid>", "businesses": [<serialized Business dicts>]}

Decimals are serialized to strings to survive Step Functions JSON round-trip.
"""

from __future__ import annotations

import asyncio
import dataclasses
import logging
import os
from datetime import datetime
from decimal import Decimal
from typing import Any

from app.application.workers.scraping_worker import ScrapingWorker
from app.domain.models.business import Business
from app.domain.models.scraping_job import ScrapingJob

logger = logging.getLogger(__name__)

_NOW_PLACEHOLDER = datetime(2000, 1, 1)


def _business_to_dict(biz: Business) -> dict[str, Any]:
    raw = dataclasses.asdict(biz)
    result: dict[str, Any] = {}
    for k, v in raw.items():
        if isinstance(v, Decimal):
            result[k] = str(v)
        elif isinstance(v, datetime):
            result[k] = v.isoformat()
        else:
            result[k] = v
    return result


async def _run(event: dict[str, Any]) -> dict[str, Any]:
    job_id: str = event["job_id"]
    category: str = event["category"]
    zone: str = event["zone"]

    job = ScrapingJob(
        id=job_id,
        category=category,
        zone=zone,
        status="running",
        order_id=None,
        records_scraped=0,
        error_message=None,
        started_at=None,
        finished_at=None,
        created_at=_NOW_PLACEHOLDER,
    )

    worker = ScrapingWorker(google_maps_api_key=os.environ["GOOGLE_MAPS_API_KEY"])
    businesses = await worker.fetch_businesses(job)

    logger.info("ScrapeBusinesses fetched %d records job_id=%s", len(businesses), job_id)
    return {"job_id": job_id, "businesses": [_business_to_dict(b) for b in businesses]}


def handler(event: dict[str, Any], context: object) -> dict[str, Any]:
    return asyncio.run(_run(event))
