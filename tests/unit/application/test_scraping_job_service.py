from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from app.application.services.scraping_job_service import ScrapingJobService
from app.domain.models.scraping_job import ScrapingJob
from app.presentation.schemas.scraping_job_schemas import CreateScrapingJobRequest

_NOW = datetime(2025, 1, 1, tzinfo=UTC)
_JOB_ID = "550e8400-e29b-41d4-a716-446655440001"


def _make_job(category: str = "restaurants", zone: str = "CABA") -> ScrapingJob:
    return ScrapingJob(
        id=_JOB_ID,
        category=category,
        zone=zone,
        status="pending",
        order_id=None,
        records_scraped=0,
        error_message=None,
        started_at=None,
        finished_at=None,
        created_at=_NOW,
    )


@pytest.fixture
def mock_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def service(mock_repo: AsyncMock) -> ScrapingJobService:
    return ScrapingJobService(mock_repo)


async def test_create_job_saves_and_returns_response(
    service: ScrapingJobService, mock_repo: AsyncMock
) -> None:
    # Arrange
    mock_repo.save.return_value = None
    payload = CreateScrapingJobRequest(category="restaurants", zone="CABA")

    # Act
    result = await service.create_job(payload)

    # Assert
    assert result.category == "restaurants"
    assert result.zone == "CABA"
    assert result.status == "pending"
    assert result.order_id is None
    assert result.records_scraped == 0
    mock_repo.save.assert_called_once()


async def test_create_job_calls_repository_save_once(
    service: ScrapingJobService, mock_repo: AsyncMock
) -> None:
    # Arrange
    mock_repo.save.return_value = None
    payload = CreateScrapingJobRequest(category="clinics", zone="Rosario")

    # Act
    await service.create_job(payload)

    # Assert
    assert mock_repo.save.call_count == 1


async def test_create_job_generates_unique_id(
    service: ScrapingJobService, mock_repo: AsyncMock
) -> None:
    # Arrange
    mock_repo.save.return_value = None
    payload = CreateScrapingJobRequest(category="restaurants", zone="CABA")

    # Act
    result1 = await service.create_job(payload)
    result2 = await service.create_job(payload)

    # Assert
    assert result1.id != result2.id


async def test_list_jobs_delegates_to_repository(
    service: ScrapingJobService, mock_repo: AsyncMock
) -> None:
    # Arrange
    job = _make_job()
    mock_repo.find_all.return_value = [job]

    # Act
    results = await service.list_jobs(status=None)

    # Assert
    assert len(results) == 1
    assert results[0].category == "restaurants"
    mock_repo.find_all.assert_called_once_with(status=None)


async def test_list_jobs_with_status_filter(
    service: ScrapingJobService, mock_repo: AsyncMock
) -> None:
    # Arrange
    mock_repo.find_all.return_value = []

    # Act
    await service.list_jobs(status="pending")

    # Assert
    mock_repo.find_all.assert_called_once_with(status="pending")


async def test_get_job_returns_none_when_not_found(
    service: ScrapingJobService, mock_repo: AsyncMock
) -> None:
    # Arrange
    mock_repo.find_by_id.return_value = None

    # Act
    result = await service.get_job("non-existent-id")

    # Assert
    assert result is None
    mock_repo.find_by_id.assert_called_once_with("non-existent-id")


async def test_get_job_returns_response_when_found(
    service: ScrapingJobService, mock_repo: AsyncMock
) -> None:
    # Arrange
    job = _make_job()
    mock_repo.find_by_id.return_value = job

    # Act
    result = await service.get_job(_JOB_ID)

    # Assert
    assert result is not None
    assert result.id == _JOB_ID
    assert result.category == "restaurants"
