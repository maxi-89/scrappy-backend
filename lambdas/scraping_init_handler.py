"""Lambda entry point for Step Functions InitJob state.

Input:  {"job_id": "<uuid>"}
Output: {"job_id": "<uuid>", "category": "<str>", "zone": "<str>"}
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from app.infrastructure.database.session import AsyncSessionLocal
from app.infrastructure.repositories.scraping_job_repository import ScrapingJobRepository

logger = logging.getLogger(__name__)


async def _run(event: dict[str, Any]) -> dict[str, Any]:
    job_id: str = event["job_id"]

    async with AsyncSessionLocal() as session:
        repo = ScrapingJobRepository(session)
        job = await repo.find_by_id(job_id)

    if job is None:
        raise ValueError(f"ScrapingJob not found: {job_id}")

    job.status = "running"
    job.started_at = datetime.now(UTC)

    async with AsyncSessionLocal() as session:
        repo = ScrapingJobRepository(session)
        await repo.update(job)

    logger.info("InitJob completed job_id=%s", job_id)
    return {"job_id": job.id, "category": job.category, "zone": job.zone}


def handler(event: dict[str, Any], context: object) -> dict[str, Any]:
    return asyncio.run(_run(event))
