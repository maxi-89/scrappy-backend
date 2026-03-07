"""Lambda entry point for Step Functions NormalizeBusinesses state.

Input:  {"job_id": "<uuid>", "businesses": [<serialized Business dicts>]}
Output: {"job_id": "<uuid>", "businesses": [<normalized and deduplicated Business dicts>]}

Applies whitespace trimming, phone normalization, category lowercasing,
and deduplication by (name, address) before persisting.
"""

from __future__ import annotations

import dataclasses
import logging
from datetime import datetime
from decimal import Decimal
from typing import Any

from app.application.workers.business_normalizer import BusinessNormalizer
from app.domain.models.business import Business

logger = logging.getLogger(__name__)


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


def handler(event: dict[str, Any], context: object) -> dict[str, Any]:
    job_id: str = event["job_id"]
    raw_businesses: list[dict[str, Any]] = event.get("businesses", [])

    businesses = [_dict_to_business(b) for b in raw_businesses]
    normalizer = BusinessNormalizer()
    normalized = normalizer.normalize(businesses)

    logger.info(
        "NormalizeBusinesses job_id=%s raw=%d normalized=%d",
        job_id,
        len(businesses),
        len(normalized),
    )
    return {"job_id": job_id, "businesses": [_business_to_dict(b) for b in normalized]}
