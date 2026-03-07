"""Unit tests for scraping_normalizer_handler."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.domain.models.business import Business

_NOW = datetime(2025, 1, 1, tzinfo=UTC)
_JOB_ID = "550e8400-e29b-41d4-a716-446655440000"


def _business_dict(**kwargs: Any) -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "id": "biz-1",
        "scraping_job_id": _JOB_ID,
        "name": "El Cuartito",
        "category": "restaurants",
        "zone": "CABA",
        "address": "Talcahuano 937",
        "phone": None,
        "website": None,
        "google_maps_url": None,
        "rating": "4.5",
        "review_count": 100,
        "latitude": "34.6037",
        "longitude": "-58.3816",
        "is_verified": False,
        "scraped_at": _NOW.isoformat(),
        "created_at": _NOW.isoformat(),
    }
    defaults.update(kwargs)
    return defaults


def test_handler_returns_normalized_businesses() -> None:
    from lambdas.scraping_normalizer_handler import handler

    event = {
        "job_id": _JOB_ID,
        "businesses": [_business_dict(name="  El Cuartito  ", category="Restaurants")],
    }
    result = handler(event, None)

    assert result["job_id"] == _JOB_ID
    assert len(result["businesses"]) == 1
    assert result["businesses"][0]["name"] == "El Cuartito"
    assert result["businesses"][0]["category"] == "restaurants"


def test_handler_deduplicates_businesses() -> None:
    from lambdas.scraping_normalizer_handler import handler

    event = {
        "job_id": _JOB_ID,
        "businesses": [
            _business_dict(id="biz-1", name="El Cuartito", address="Talcahuano 937"),
            _business_dict(id="biz-2", name="El Cuartito", address="Talcahuano 937"),
        ],
    }
    result = handler(event, None)

    assert len(result["businesses"]) == 1


def test_handler_empty_list_returns_empty() -> None:
    from lambdas.scraping_normalizer_handler import handler

    event = {"job_id": _JOB_ID, "businesses": []}
    result = handler(event, None)

    assert result["job_id"] == _JOB_ID
    assert result["businesses"] == []


def test_handler_preserves_records_count() -> None:
    from lambdas.scraping_normalizer_handler import handler

    event = {
        "job_id": _JOB_ID,
        "businesses": [
            _business_dict(id="biz-1", name="El Cuartito", address="Talcahuano 937"),
            _business_dict(id="biz-2", name="La Americana", address="Callao 83"),
        ],
    }
    result = handler(event, None)

    assert len(result["businesses"]) == 2
