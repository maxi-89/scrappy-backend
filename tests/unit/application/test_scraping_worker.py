from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.application.workers.scraping_worker import ScrapingWorker
from app.domain.models.business import Business
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


def _make_business(name: str = "Biz A") -> Business:
    return Business(
        id="biz-1",
        scraping_job_id=_JOB_ID,
        name=name,
        category="restaurants",
        zone="CABA",
        address=None,
        phone=None,
        website=None,
        google_maps_url=None,
        rating=Decimal("4.0"),
        review_count=10,
        latitude=None,
        longitude=None,
        is_verified=False,
        scraped_at=_NOW,
        created_at=_NOW,
    )


def _make_session_factory(job_repo: AsyncMock, biz_repo: AsyncMock) -> MagicMock:
    """Returns a session factory whose context manager yields a mock session."""
    session = AsyncMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=False)
    factory = MagicMock(return_value=cm)
    return factory


@pytest.fixture
def mock_job_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.find_by_id.return_value = _valid_job()
    return repo


@pytest.fixture
def mock_biz_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def session_factory(mock_job_repo: AsyncMock, mock_biz_repo: AsyncMock) -> MagicMock:
    return _make_session_factory(mock_job_repo, mock_biz_repo)


def _make_worker(session_factory: MagicMock) -> ScrapingWorker:
    return ScrapingWorker(
        session_factory=session_factory,
        google_maps_api_key="test-key",
    )


# ---------------------------------------------------------------------------
# run_by_id — happy path
# ---------------------------------------------------------------------------


async def test_run_by_id_marks_job_running_then_completed(
    session_factory: MagicMock,
) -> None:
    # Arrange
    businesses = [_make_business("Biz A"), _make_business("Biz B"), _make_business("Biz C")]
    worker = _make_worker(session_factory)

    with (
        patch.object(worker, "_fetch_businesses", return_value=businesses) as mock_fetch,
        patch("app.application.workers.scraping_worker.ScrapingJobRepository") as MockJobRepo,
        patch("app.application.workers.scraping_worker.BusinessRepository") as MockBizRepo,
    ):
        snapshots: list[ScrapingJob] = []

        async def capture_update(job: ScrapingJob) -> None:
            snapshots.append(replace(job))

        mock_job_repo = AsyncMock()
        mock_job_repo.find_by_id.return_value = _valid_job()
        mock_job_repo.update.side_effect = capture_update
        MockJobRepo.return_value = mock_job_repo
        mock_biz_repo = AsyncMock()
        MockBizRepo.return_value = mock_biz_repo

        # Act
        await worker.run_by_id(_JOB_ID)

    # Assert: update() called twice (running + completed)
    assert len(snapshots) == 2
    assert snapshots[0].status == "running"
    assert snapshots[0].started_at is not None
    assert snapshots[1].status == "completed"
    assert snapshots[1].records_scraped == 3
    assert snapshots[1].finished_at is not None
    mock_biz_repo.save_many.assert_called_once_with(businesses)
    mock_fetch.assert_called_once()


# ---------------------------------------------------------------------------
# run_by_id — failure path
# ---------------------------------------------------------------------------


async def test_run_by_id_marks_job_failed_on_api_exception(
    session_factory: MagicMock,
) -> None:
    # Arrange
    worker = _make_worker(session_factory)

    with (
        patch.object(worker, "_fetch_businesses", side_effect=RuntimeError("API unavailable")),
        patch("app.application.workers.scraping_worker.ScrapingJobRepository") as MockJobRepo,
        patch("app.application.workers.scraping_worker.BusinessRepository"),
    ):
        snapshots: list[ScrapingJob] = []

        async def capture_update(job: ScrapingJob) -> None:
            snapshots.append(replace(job))

        mock_job_repo = AsyncMock()
        mock_job_repo.find_by_id.return_value = _valid_job()
        mock_job_repo.update.side_effect = capture_update
        MockJobRepo.return_value = mock_job_repo

        # Act
        await worker.run_by_id(_JOB_ID)

    # Assert: running then failed
    assert len(snapshots) == 2
    assert snapshots[0].status == "running"
    assert snapshots[1].status == "failed"
    assert snapshots[1].error_message == "API unavailable"
    assert snapshots[1].finished_at is not None


# ---------------------------------------------------------------------------
# run_by_id — job not found
# ---------------------------------------------------------------------------


async def test_run_by_id_does_nothing_when_job_not_found(
    session_factory: MagicMock,
) -> None:
    # Arrange
    worker = _make_worker(session_factory)

    with (
        patch("app.application.workers.scraping_worker.ScrapingJobRepository") as MockJobRepo,
        patch("app.application.workers.scraping_worker.BusinessRepository") as MockBizRepo,
    ):
        mock_job_repo = AsyncMock()
        mock_job_repo.find_by_id.return_value = None
        MockJobRepo.return_value = mock_job_repo
        mock_biz_repo = AsyncMock()
        MockBizRepo.return_value = mock_biz_repo

        # Act
        await worker.run_by_id(_JOB_ID)

    # Assert
    mock_job_repo.update.assert_not_called()
    mock_biz_repo.save_many.assert_not_called()


# ---------------------------------------------------------------------------
# _map_to_domain
# ---------------------------------------------------------------------------


def test_map_to_domain_returns_none_for_empty_name() -> None:
    worker = ScrapingWorker(session_factory=MagicMock(), google_maps_api_key="key")
    job = _valid_job()
    result = worker._map_to_domain({}, job, _NOW)  # type: ignore[arg-type]
    assert result is None


def test_map_to_domain_handles_missing_geometry() -> None:
    worker = ScrapingWorker(session_factory=MagicMock(), google_maps_api_key="key")
    job = _valid_job()
    detail: dict[str, object] = {"name": "Some Biz"}
    result = worker._map_to_domain(detail, job, _NOW)
    assert result is not None
    assert result.latitude is None
    assert result.longitude is None


def test_map_to_domain_converts_rating_and_coordinates() -> None:
    worker = ScrapingWorker(session_factory=MagicMock(), google_maps_api_key="key")
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
    result = worker._map_to_domain(detail, job, _NOW)
    assert result is not None
    assert result.name == "El Cuartito"
    assert result.rating == Decimal("4.5")
    assert result.review_count == 1200
    assert result.latitude == Decimal("-34.5997")
    assert result.longitude == Decimal("-58.3819")
    assert result.is_verified is False


def test_map_to_domain_converts_empty_strings_to_none() -> None:
    worker = ScrapingWorker(session_factory=MagicMock(), google_maps_api_key="key")
    job = _valid_job()
    detail: dict[str, object] = {
        "name": "Some Biz",
        "formatted_address": "",
        "formatted_phone_number": "",
        "website": "",
        "url": "",
    }
    result = worker._map_to_domain(detail, job, _NOW)
    assert result is not None
    assert result.address is None
    assert result.phone is None
    assert result.website is None
    assert result.google_maps_url is None
