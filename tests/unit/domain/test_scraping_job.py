from datetime import UTC, datetime

import pytest

from app.domain.models.scraping_job import ScrapingJob

_NOW = datetime(2025, 1, 1, tzinfo=UTC)

_VALID_ID = "550e8400-e29b-41d4-a716-446655440000"


def _valid_job(**overrides: object) -> ScrapingJob:
    defaults: dict[str, object] = {
        "id": _VALID_ID,
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


def test_valid_scraping_job_created_successfully() -> None:
    # Arrange / Act
    job = _valid_job()

    # Assert
    assert job.id == _VALID_ID
    assert job.category == "restaurants"
    assert job.zone == "CABA"
    assert job.status == "pending"
    assert job.order_id is None
    assert job.records_scraped == 0
    assert job.created_at == _NOW


def test_scraping_job_order_id_can_be_set() -> None:
    job = _valid_job(order_id="some-order-id")
    assert job.order_id == "some-order-id"


def test_empty_category_raises_value_error() -> None:
    with pytest.raises(ValueError, match="category"):
        _valid_job(category="")


def test_whitespace_only_category_raises_value_error() -> None:
    with pytest.raises(ValueError, match="category"):
        _valid_job(category="   ")


def test_empty_zone_raises_value_error() -> None:
    with pytest.raises(ValueError, match="zone"):
        _valid_job(zone="")


def test_whitespace_only_zone_raises_value_error() -> None:
    with pytest.raises(ValueError, match="zone"):
        _valid_job(zone="   ")


def test_invalid_status_raises_value_error() -> None:
    with pytest.raises(ValueError, match="status"):
        _valid_job(status="unknown")


def test_valid_statuses_are_accepted() -> None:
    for status in ("pending", "running", "completed", "failed"):
        job = _valid_job(status=status)
        assert job.status == status


def test_negative_records_scraped_raises_value_error() -> None:
    with pytest.raises(ValueError, match="records_scraped"):
        _valid_job(records_scraped=-1)


def test_zero_records_scraped_is_valid() -> None:
    job = _valid_job(records_scraped=0)
    assert job.records_scraped == 0
