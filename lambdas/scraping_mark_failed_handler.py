"""Lambda entry point for Step Functions MarkFailed state (Catch target).

Step Functions Catch with ResultPath="$.error" merges error info into the original
state input, so this handler receives:

Input:  {
          "job_id": "<uuid>",
          [other original fields...],
          "error": {"Error": "<ErrorType>", "Cause": "<message>"}
        }
Output: {"job_id": "<uuid>"}
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
    error_info: dict[str, Any] = event.get("error", {})
    error_message: str = str(error_info.get("Cause", "Unknown error"))

    async with AsyncSessionLocal() as session:
        repo = ScrapingJobRepository(session)
        job = await repo.find_by_id(job_id)

    if job is None:
        logger.error("MarkFailed: ScrapingJob not found job_id=%s", job_id)
        return {"job_id": job_id}

    job.status = "failed"
    job.error_message = error_message
    job.finished_at = datetime.now(UTC)

    async with AsyncSessionLocal() as session:
        repo = ScrapingJobRepository(session)
        await repo.update(job)

    logger.error("MarkFailed completed job_id=%s error=%s", job_id, error_message)
    return {"job_id": job_id}


def handler(event: dict[str, Any], context: object) -> dict[str, Any]:
    return asyncio.run(_run(event))
