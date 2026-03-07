"""Unit tests for Lambda handlers: init, scraper, saver, mark_failed."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.models.business import Business
from app.domain.models.scraping_job import ScrapingJob

_NOW = datetime(2025, 1, 1, tzinfo=UTC)
_JOB_ID = "550e8400-e29b-41d4-a716-446655440000"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _valid_job(**overrides: object) -> ScrapingJob:
    defaults: dict[str, object] = {
        "id": _JOB_ID,
        "category": "restaurants",
        "zone": "CABA",
        "status": "pending",
        "order_id": None,
        "records_scraped": 0,
        "error_message": None,
        "started_at": None,
        "finished_at": None,
        "created_at": _NOW,
    }
    defaults.update(overrides)
    return ScrapingJob(**defaults)  # type: ignore[arg-type]


def _valid_business() -> Business:
    return Business(
        id="biz-1",
        scraping_job_id=_JOB_ID,
        name="El Cuartito",
        category="restaurants",
        zone="CABA",
        address="Talcahuano 937",
        phone=None,
        website=None,
        google_maps_url=None,
        rating=Decimal("4.5"),
        review_count=100,
        latitude=Decimal("-34.5997"),
        longitude=Decimal("-58.3819"),
        is_verified=False,
        scraped_at=_NOW,
        created_at=_NOW,
    )


def _make_session_factory(job_repo: AsyncMock) -> MagicMock:
    session = AsyncMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=False)
    return MagicMock(return_value=cm)


# ---------------------------------------------------------------------------
# scraping_init_handler
# ---------------------------------------------------------------------------


async def test_init_handler_marks_job_running_and_returns_category_zone() -> None:
    from lambdas.scraping_init_handler import _run

    job = _valid_job()

    with (
        patch("lambdas.scraping_init_handler.AsyncSessionLocal") as MockFactory,
        patch("lambdas.scraping_init_handler.ScrapingJobRepository") as MockRepo,
    ):
        mock_repo = AsyncMock()
        mock_repo.find_by_id.return_value = job
        mock_repo.update.return_value = None
        MockRepo.return_value = mock_repo

        session = AsyncMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=session)
        cm.__aexit__ = AsyncMock(return_value=False)
        MockFactory.return_value = cm

        result = await _run({"job_id": _JOB_ID})

    assert result == {"job_id": _JOB_ID, "category": "restaurants", "zone": "CABA"}
    assert job.status == "running"
    assert job.started_at is not None
    mock_repo.update.assert_called_once_with(job)


async def test_init_handler_raises_when_job_not_found() -> None:
    from lambdas.scraping_init_handler import _run

    with (
        patch("lambdas.scraping_init_handler.AsyncSessionLocal") as MockFactory,
        patch("lambdas.scraping_init_handler.ScrapingJobRepository") as MockRepo,
    ):
        mock_repo = AsyncMock()
        mock_repo.find_by_id.return_value = None
        MockRepo.return_value = mock_repo

        session = AsyncMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=session)
        cm.__aexit__ = AsyncMock(return_value=False)
        MockFactory.return_value = cm

        with pytest.raises(ValueError, match="not found"):
            await _run({"job_id": _JOB_ID})


# ---------------------------------------------------------------------------
# scraping_scraper_handler
# ---------------------------------------------------------------------------


async def test_scraper_handler_calls_fetch_and_serializes_businesses() -> None:
    from lambdas.scraping_scraper_handler import _run

    biz = _valid_business()

    with (
        patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "test-key"}),
        patch("lambdas.scraping_scraper_handler.ScrapingWorker") as MockWorker,
    ):
        mock_worker = AsyncMock()
        mock_worker.fetch_businesses = AsyncMock(return_value=[biz])
        MockWorker.return_value = mock_worker

        result = await _run({"job_id": _JOB_ID, "category": "restaurants", "zone": "CABA"})

    assert result["job_id"] == _JOB_ID
    assert len(result["businesses"]) == 1
    biz_dict = result["businesses"][0]
    # Decimals are serialized to strings
    assert biz_dict["rating"] == "4.5"
    assert biz_dict["latitude"] == "-34.5997"
    assert biz_dict["name"] == "El Cuartito"


async def test_scraper_handler_instantiates_worker_with_api_key() -> None:
    """Scraper handler passes GOOGLE_MAPS_API_KEY to the worker — no DB calls needed."""
    from lambdas.scraping_scraper_handler import _run

    with (
        patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "my-key"}),
        patch("lambdas.scraping_scraper_handler.ScrapingWorker") as MockWorker,
    ):
        mock_worker = AsyncMock()
        mock_worker.fetch_businesses = AsyncMock(return_value=[])
        MockWorker.return_value = mock_worker

        await _run({"job_id": _JOB_ID, "category": "restaurants", "zone": "CABA"})

    MockWorker.assert_called_once_with(google_maps_api_key="my-key")


# ---------------------------------------------------------------------------
# scraping_saver_handler
# ---------------------------------------------------------------------------


def _business_event_dict() -> dict[str, object]:
    biz = _valid_business()
    return {
        "id": biz.id,
        "scraping_job_id": biz.scraping_job_id,
        "name": biz.name,
        "category": biz.category,
        "zone": biz.zone,
        "address": biz.address,
        "phone": biz.phone,
        "website": biz.website,
        "google_maps_url": biz.google_maps_url,
        "rating": str(biz.rating),
        "review_count": biz.review_count,
        "latitude": str(biz.latitude),
        "longitude": str(biz.longitude),
        "is_verified": biz.is_verified,
        "scraped_at": biz.scraped_at.isoformat(),
        "created_at": biz.created_at.isoformat(),
    }


async def test_saver_handler_saves_businesses_and_marks_completed() -> None:
    from lambdas.scraping_saver_handler import _run

    job = _valid_job(status="running")

    with (
        patch("lambdas.scraping_saver_handler.AsyncSessionLocal") as MockFactory,
        patch("lambdas.scraping_saver_handler.BusinessRepository") as MockBizRepo,
        patch("lambdas.scraping_saver_handler.ScrapingJobRepository") as MockJobRepo,
    ):
        mock_biz_repo = AsyncMock()
        MockBizRepo.return_value = mock_biz_repo

        mock_job_repo = AsyncMock()
        mock_job_repo.find_by_id.return_value = job
        mock_job_repo.update.return_value = None
        MockJobRepo.return_value = mock_job_repo

        session = AsyncMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=session)
        cm.__aexit__ = AsyncMock(return_value=False)
        MockFactory.return_value = cm

        event = {"job_id": _JOB_ID, "businesses": [_business_event_dict()]}
        result = await _run(event)

    assert result == {"job_id": _JOB_ID, "records_saved": 1}
    assert job.status == "completed"
    assert job.records_scraped == 1
    assert job.finished_at is not None
    mock_biz_repo.save_many.assert_called_once()
    mock_job_repo.update.assert_called_once_with(job)


async def test_saver_handler_raises_when_job_not_found() -> None:
    from lambdas.scraping_saver_handler import _run

    with (
        patch("lambdas.scraping_saver_handler.AsyncSessionLocal") as MockFactory,
        patch("lambdas.scraping_saver_handler.BusinessRepository") as MockBizRepo,
        patch("lambdas.scraping_saver_handler.ScrapingJobRepository") as MockJobRepo,
    ):
        MockBizRepo.return_value = AsyncMock()
        mock_job_repo = AsyncMock()
        mock_job_repo.find_by_id.return_value = None
        MockJobRepo.return_value = mock_job_repo

        session = AsyncMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=session)
        cm.__aexit__ = AsyncMock(return_value=False)
        MockFactory.return_value = cm

        with pytest.raises(ValueError, match="not found"):
            await _run({"job_id": _JOB_ID, "businesses": []})


# ---------------------------------------------------------------------------
# scraping_mark_failed_handler
# ---------------------------------------------------------------------------


async def test_mark_failed_handler_sets_status_failed_with_error_message() -> None:
    from lambdas.scraping_mark_failed_handler import _run

    job = _valid_job(status="running")

    with (
        patch("lambdas.scraping_mark_failed_handler.AsyncSessionLocal") as MockFactory,
        patch("lambdas.scraping_mark_failed_handler.ScrapingJobRepository") as MockRepo,
    ):
        mock_repo = AsyncMock()
        mock_repo.find_by_id.return_value = job
        mock_repo.update.return_value = None
        MockRepo.return_value = mock_repo

        session = AsyncMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=session)
        cm.__aexit__ = AsyncMock(return_value=False)
        MockFactory.return_value = cm

        sfn_catch_event = {
            "job_id": _JOB_ID,
            "error": {"Error": "RuntimeError", "Cause": "Google API unavailable"},
        }
        result = await _run(sfn_catch_event)

    assert result == {"job_id": _JOB_ID}
    assert job.status == "failed"
    assert job.error_message == "Google API unavailable"
    assert job.finished_at is not None
    mock_repo.update.assert_called_once_with(job)


async def test_mark_failed_handler_returns_gracefully_when_job_not_found() -> None:
    from lambdas.scraping_mark_failed_handler import _run

    with (
        patch("lambdas.scraping_mark_failed_handler.AsyncSessionLocal") as MockFactory,
        patch("lambdas.scraping_mark_failed_handler.ScrapingJobRepository") as MockRepo,
    ):
        mock_repo = AsyncMock()
        mock_repo.find_by_id.return_value = None
        MockRepo.return_value = mock_repo

        session = AsyncMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=session)
        cm.__aexit__ = AsyncMock(return_value=False)
        MockFactory.return_value = cm

        result = await _run({"job_id": _JOB_ID, "error": {"Error": "E", "Cause": "c"}})

    assert result == {"job_id": _JOB_ID}
    mock_repo.update.assert_not_called()
