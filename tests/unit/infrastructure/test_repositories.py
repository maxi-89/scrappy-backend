"""Infrastructure tests for ScrapingJobRepository.update() and BusinessRepository."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.domain.models.business import Business
from app.domain.models.scraping_job import ScrapingJob
from app.infrastructure.database.orm_models import Base
from app.infrastructure.repositories.business_repository import BusinessRepository
from app.infrastructure.repositories.scraping_job_repository import ScrapingJobRepository

_NOW = datetime(2025, 1, 1, tzinfo=UTC)
_NOW_NAIVE = datetime(2025, 1, 1)  # SQLite strips tz info on round-trip
_JOB_ID = "job-001"
_BIZ_ID = "biz-001"


@pytest.fixture
async def session() -> AsyncSession:  # type: ignore[misc]
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


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


def _valid_business(**overrides: object) -> Business:
    defaults: dict[str, object] = {
        "id": _BIZ_ID,
        "scraping_job_id": _JOB_ID,
        "name": "El Cuartito",
        "category": "restaurants",
        "zone": "CABA",
        "address": "Talcahuano 937",
        "phone": "+54 11 4816-1758",
        "website": "https://elcuartito.com.ar",
        "google_maps_url": "https://maps.google.com/?cid=1",
        "rating": Decimal("4.5"),
        "review_count": 1200,
        "latitude": Decimal("-34.5997"),
        "longitude": Decimal("-58.3819"),
        "is_verified": False,
        "scraped_at": _NOW,
        "created_at": _NOW,
    }
    defaults.update(overrides)
    return Business(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# ScrapingJobRepository.update()
# ---------------------------------------------------------------------------


async def test_scraping_job_repository_update_modifies_status(session: AsyncSession) -> None:
    # Arrange
    repo = ScrapingJobRepository(session)
    job = _valid_job()
    await repo.save(job)

    # Act
    job.status = "running"
    job.started_at = _NOW
    await repo.update(job)

    # Assert
    updated = await repo.find_by_id(_JOB_ID)
    assert updated is not None
    assert updated.status == "running"
    assert updated.started_at == _NOW_NAIVE


async def test_scraping_job_repository_update_sets_completed(session: AsyncSession) -> None:
    # Arrange
    repo = ScrapingJobRepository(session)
    job = _valid_job()
    await repo.save(job)

    # Act
    job.status = "completed"
    job.records_scraped = 42
    job.finished_at = _NOW
    await repo.update(job)

    # Assert
    updated = await repo.find_by_id(_JOB_ID)
    assert updated is not None
    assert updated.status == "completed"
    assert updated.records_scraped == 42
    assert updated.finished_at == _NOW_NAIVE


async def test_scraping_job_repository_update_sets_failed(session: AsyncSession) -> None:
    # Arrange
    repo = ScrapingJobRepository(session)
    job = _valid_job()
    await repo.save(job)

    # Act
    job.status = "failed"
    job.error_message = "API timeout"
    job.finished_at = _NOW
    await repo.update(job)

    # Assert
    updated = await repo.find_by_id(_JOB_ID)
    assert updated is not None
    assert updated.status == "failed"
    assert updated.error_message == "API timeout"
    assert updated.finished_at == _NOW_NAIVE


# ---------------------------------------------------------------------------
# BusinessRepository
# ---------------------------------------------------------------------------


async def test_business_repository_save_many_and_find_by_job_id(
    session: AsyncSession,
) -> None:
    # Arrange — save the parent job first (FK constraint)
    job_repo = ScrapingJobRepository(session)
    await job_repo.save(_valid_job())

    biz_repo = BusinessRepository(session)
    businesses = [
        _valid_business(id="biz-1", name="Biz A"),
        _valid_business(id="biz-2", name="Biz B"),
    ]

    # Act
    await biz_repo.save_many(businesses)

    # Assert
    results = await biz_repo.find_by_job_id(_JOB_ID)
    assert len(results) == 2
    names = {b.name for b in results}
    assert names == {"Biz A", "Biz B"}


async def test_business_repository_find_by_job_id_returns_empty_for_unknown_job(
    session: AsyncSession,
) -> None:
    # Arrange
    biz_repo = BusinessRepository(session)

    # Act
    results = await biz_repo.find_by_job_id("unknown-job-id")

    # Assert
    assert results == []


async def test_business_repository_save_many_preserves_all_fields(
    session: AsyncSession,
) -> None:
    # Arrange — save parent job first
    job_repo = ScrapingJobRepository(session)
    await job_repo.save(_valid_job())

    biz_repo = BusinessRepository(session)
    biz = _valid_business()

    # Act
    await biz_repo.save_many([biz])

    # Assert
    results = await biz_repo.find_by_job_id(_JOB_ID)
    assert len(results) == 1
    result = results[0]
    assert result.name == "El Cuartito"
    assert result.rating == Decimal("4.5")
    assert result.review_count == 1200
    assert result.is_verified is False
    assert result.address == "Talcahuano 937"
    assert result.scraping_job_id == _JOB_ID


async def test_business_repository_save_many_empty_list_is_noop(
    session: AsyncSession,
) -> None:
    # Arrange
    biz_repo = BusinessRepository(session)

    # Act — should not raise
    await biz_repo.save_many([])

    # Assert
    results = await biz_repo.find_by_job_id(_JOB_ID)
    assert results == []


# ---------------------------------------------------------------------------
# ScrapingJobRepository.find_all()
# ---------------------------------------------------------------------------


async def test_scraping_job_repository_find_all_no_filter(session: AsyncSession) -> None:
    # Arrange
    repo = ScrapingJobRepository(session)
    await repo.save(_valid_job(id="j1", status="pending"))
    await repo.save(_valid_job(id="j2", status="completed"))

    # Act
    results = await repo.find_all()

    # Assert
    assert len(results) == 2


async def test_scraping_job_repository_find_all_with_status_filter(
    session: AsyncSession,
) -> None:
    # Arrange
    repo = ScrapingJobRepository(session)
    await repo.save(_valid_job(id="j1", status="pending"))
    await repo.save(_valid_job(id="j2", status="completed"))

    # Act
    pending = await repo.find_all(status="pending")

    # Assert
    assert len(pending) == 1
    assert pending[0].status == "pending"
