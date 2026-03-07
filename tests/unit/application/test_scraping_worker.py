from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from app.application.workers.scraping_worker import ScrapingWorker
from app.domain.models.scraping_job import ScrapingJob

_NOW = datetime(2025, 1, 1, tzinfo=UTC)
_JOB_ID = "550e8400-e29b-41d4-a716-446655440000"


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


def _make_worker() -> ScrapingWorker:
    return ScrapingWorker(google_maps_api_key="test-key")


# ---------------------------------------------------------------------------
# map_to_domain
# ---------------------------------------------------------------------------


def test_map_to_domain_returns_none_for_empty_name() -> None:
    worker = _make_worker()
    job = _valid_job()
    result = worker.map_to_domain({}, job, _NOW)  # type: ignore[arg-type]
    assert result is None


def test_map_to_domain_handles_missing_geometry() -> None:
    worker = _make_worker()
    job = _valid_job()
    detail: dict[str, object] = {"name": "Some Biz"}
    result = worker.map_to_domain(detail, job, _NOW)
    assert result is not None
    assert result.latitude is None
    assert result.longitude is None


def test_map_to_domain_converts_rating_and_coordinates() -> None:
    worker = _make_worker()
    job = _valid_job()
    detail: dict[str, object] = {
        "name": "El Cuartito",
        "formatted_address": "Talcahuano 937",
        "formatted_phone_number": "+54 11 4816-1758",
        "website": "https://elcuartito.com.ar",
        "url": "https://maps.google.com/?cid=123",
        "rating": 4.5,
        "user_ratings_total": 1200,
        "geometry": {"location": {"lat": -34.5997, "lng": -58.3819}},
    }
    result = worker.map_to_domain(detail, job, _NOW)
    assert result is not None
    assert result.name == "El Cuartito"
    assert result.rating == Decimal("4.5")
    assert result.review_count == 1200
    assert result.latitude == Decimal("-34.5997")
    assert result.longitude == Decimal("-58.3819")
    assert result.is_verified is False


def test_map_to_domain_converts_empty_strings_to_none() -> None:
    worker = _make_worker()
    job = _valid_job()
    detail: dict[str, object] = {
        "name": "Some Biz",
        "formatted_address": "",
        "formatted_phone_number": "",
        "website": "",
        "url": "",
    }
    result = worker.map_to_domain(detail, job, _NOW)
    assert result is not None
    assert result.address is None
    assert result.phone is None
    assert result.website is None
    assert result.google_maps_url is None


# ---------------------------------------------------------------------------
# fetch_businesses
# ---------------------------------------------------------------------------


async def test_fetch_businesses_returns_businesses_from_places_api() -> None:
    worker = _make_worker()
    job = _valid_job()

    mock_places_response = {"results": [{"place_id": "place_abc"}]}
    mock_detail_response = {
        "result": {"name": "El Cuartito", "rating": 4.5, "user_ratings_total": 100}
    }

    with patch("app.application.workers.scraping_worker.googlemaps.Client") as MockGmaps:
        mock_client = MagicMock()
        MockGmaps.return_value = mock_client
        mock_client.places = MagicMock(return_value=mock_places_response)
        mock_client.place = MagicMock(return_value=mock_detail_response)

        businesses = await worker.fetch_businesses(job)

    assert len(businesses) == 1
    assert businesses[0].name == "El Cuartito"
    assert businesses[0].scraping_job_id == _JOB_ID


async def test_fetch_businesses_skips_result_without_place_id() -> None:
    worker = _make_worker()
    job = _valid_job()

    mock_places_response = {"results": [{"place_id": ""}, {"no_place_id": True}]}

    with patch("app.application.workers.scraping_worker.googlemaps.Client") as MockGmaps:
        mock_client = MagicMock()
        MockGmaps.return_value = mock_client
        mock_client.places = MagicMock(return_value=mock_places_response)

        businesses = await worker.fetch_businesses(job)

    assert businesses == []
    mock_client.place.assert_not_called()


async def test_fetch_businesses_paginates_up_to_max_pages() -> None:
    worker = _make_worker()
    job = _valid_job()

    page1 = {"results": [{"place_id": "p1"}], "next_page_token": "token1"}
    page2 = {"results": [{"place_id": "p2"}], "next_page_token": "token2"}
    page3 = {"results": [{"place_id": "p3"}]}
    mock_detail = {"result": {"name": "Biz", "rating": 4.0, "user_ratings_total": 10}}

    with (
        patch("app.application.workers.scraping_worker.googlemaps.Client") as MockGmaps,
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        mock_client = MagicMock()
        MockGmaps.return_value = mock_client
        mock_client.places = MagicMock(side_effect=[page1, page2, page3])
        mock_client.place = MagicMock(return_value=mock_detail)

        businesses = await worker.fetch_businesses(job)

    assert len(businesses) == 3
