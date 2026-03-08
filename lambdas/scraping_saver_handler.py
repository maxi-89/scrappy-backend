"""Lambda entry point for Step Functions SaveBusinesses state.

Input:  {"job_id": "<uuid>", "businesses": [<serialized Business dicts>]}
Output: {"job_id": "<uuid>", "records_saved": <int>}

After saving businesses it:
  1. Generates a result file (CSV / Excel / JSON) based on the associated order format.
  2. Uploads the file to S3.
  3. Marks the order as completed with result_path set.
  4. Marks the scraping job as completed.
"""

from __future__ import annotations

import asyncio
import csv
import io
import json
import logging
import os
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import boto3
import openpyxl

from app.domain.models.business import Business
from app.infrastructure.database.session import AsyncSessionLocal
from app.infrastructure.repositories.business_repository import BusinessRepository
from app.infrastructure.repositories.order_repository import OrderRepository
from app.infrastructure.repositories.scraping_job_repository import ScrapingJobRepository

logger = logging.getLogger(__name__)

_RESULTS_BUCKET = os.environ.get("RESULTS_BUCKET", "")

_RESULT_FIELDS = ["name", "category", "zone", "address", "phone", "website", "rating", "review_count"]

_CONTENT_TYPES = {
    "csv": "text/csv",
    "excel": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "json": "application/json",
}


def _dict_to_business(data: dict[str, Any]) -> Business:
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


def _to_row(b: Business) -> dict[str, Any]:
    return {
        "name": b.name,
        "category": b.category,
        "zone": b.zone,
        "address": b.address or "",
        "phone": b.phone or "",
        "website": b.website or "",
        "rating": str(b.rating) if b.rating is not None else "",
        "review_count": b.review_count,
    }


def _generate_csv(businesses: list[Business]) -> bytes:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=_RESULT_FIELDS)
    writer.writeheader()
    for b in businesses:
        writer.writerow(_to_row(b))
    return buf.getvalue().encode("utf-8")


def _generate_excel(businesses: list[Business]) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(_RESULT_FIELDS)
    for b in businesses:
        row = _to_row(b)
        ws.append([row[f] for f in _RESULT_FIELDS])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _generate_json(businesses: list[Business]) -> bytes:
    records = [_to_row(b) for b in businesses]
    return json.dumps(records, ensure_ascii=False, indent=2).encode("utf-8")


def _generate_file(businesses: list[Business], fmt: str) -> bytes:
    if fmt == "csv":
        return _generate_csv(businesses)
    if fmt == "excel":
        return _generate_excel(businesses)
    return _generate_json(businesses)


def _upload_to_s3(key: str, data: bytes, content_type: str) -> None:
    client = boto3.client("s3")
    client.put_object(Bucket=_RESULTS_BUCKET, Key=key, Body=data, ContentType=content_type)


async def _run(event: dict[str, Any]) -> dict[str, Any]:
    job_id: str = event["job_id"]
    raw_businesses: list[dict[str, Any]] = event.get("businesses", [])

    businesses = [_dict_to_business(b) for b in raw_businesses]

    # Save businesses to DB
    async with AsyncSessionLocal() as session:
        biz_repo = BusinessRepository(session)
        await biz_repo.save_many(businesses)

    # Load scraping job
    async with AsyncSessionLocal() as session:
        job_repo = ScrapingJobRepository(session)
        job = await job_repo.find_by_id(job_id)

    if job is None:
        raise ValueError(f"ScrapingJob not found: {job_id}")

    now = datetime.now(UTC)

    # If linked to an order: generate result file, upload to S3, update order
    if job.order_id and _RESULTS_BUCKET:
        async with AsyncSessionLocal() as session:
            order_repo = OrderRepository(session)
            order = await order_repo.find_by_id(job.order_id)

        if order is not None:
            fmt = order.format
            file_data = _generate_file(businesses, fmt)
            ext = "xlsx" if fmt == "excel" else fmt
            result_key = f"results/{order.id}.{ext}"
            content_type = _CONTENT_TYPES.get(fmt, "application/octet-stream")
            _upload_to_s3(result_key, file_data, content_type)

            order.status = "completed"
            order.completed_at = now
            order.result_path = result_key

            async with AsyncSessionLocal() as session:
                order_repo = OrderRepository(session)
                await order_repo.update(order)

            logger.info("Order %s marked completed result_path=%s", order.id, result_key)

    # Mark scraping job as completed
    job.status = "completed"
    job.records_scraped = len(businesses)
    job.finished_at = now

    async with AsyncSessionLocal() as session:
        job_repo = ScrapingJobRepository(session)
        await job_repo.update(job)

    logger.info("SaveBusinesses completed job_id=%s records=%d", job_id, len(businesses))
    return {"job_id": job_id, "records_saved": len(businesses)}


def handler(event: dict[str, Any], context: object) -> dict[str, Any]:
    return asyncio.run(_run(event))
