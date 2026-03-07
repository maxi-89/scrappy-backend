from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.infrastructure.dependencies import (
    get_admin_key,
    get_scraping_job_service,
    get_sfn_client,
)
from app.presentation.schemas.scraping_job_schemas import ScrapingJobResponse
from main import app

_NOW = datetime(2025, 1, 1, tzinfo=UTC)

_SAMPLE_RESPONSE = ScrapingJobResponse(
    id="550e8400-e29b-41d4-a716-446655440001",
    category="restaurants",
    zone="CABA",
    status="pending",
    order_id=None,
    records_scraped=0,
    error_message=None,
    started_at=None,
    finished_at=None,
    created_at=_NOW,
)


@pytest.fixture(autouse=True)
def clear_overrides() -> None:  # type: ignore[misc]
    yield
    app.dependency_overrides.clear()


def _bypass_admin_key() -> str:
    return "test-admin-key"


@pytest.fixture
def mock_service() -> AsyncMock:
    svc = AsyncMock()
    svc.create_job.return_value = _SAMPLE_RESPONSE
    svc.list_jobs.return_value = [_SAMPLE_RESPONSE]
    svc.get_job.return_value = _SAMPLE_RESPONSE
    return svc


@pytest.fixture
def mock_sfn() -> MagicMock:
    sfn = MagicMock()
    sfn.start_execution = MagicMock()
    return sfn


# ---------------------------------------------------------------------------
# POST /admin/scraping-jobs
# ---------------------------------------------------------------------------


async def test_create_job_returns_202(mock_service: AsyncMock, mock_sfn: MagicMock) -> None:
    # Arrange
    app.dependency_overrides[get_admin_key] = _bypass_admin_key
    app.dependency_overrides[get_scraping_job_service] = lambda: mock_service
    app.dependency_overrides[get_sfn_client] = lambda: mock_sfn

    # Act
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/admin/scraping-jobs",
            json={"category": "restaurants", "zone": "CABA"},
        )

    # Assert
    assert response.status_code == 202
    body = response.json()
    assert body["category"] == "restaurants"
    assert body["zone"] == "CABA"
    assert body["status"] == "pending"
    mock_service.create_job.assert_called_once()


async def test_create_job_missing_category_returns_422(
    mock_service: AsyncMock, mock_sfn: MagicMock
) -> None:
    # Arrange
    app.dependency_overrides[get_admin_key] = _bypass_admin_key
    app.dependency_overrides[get_scraping_job_service] = lambda: mock_service
    app.dependency_overrides[get_sfn_client] = lambda: mock_sfn

    # Act
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/admin/scraping-jobs",
            json={"zone": "CABA"},
        )

    # Assert
    assert response.status_code == 422


async def test_create_job_missing_zone_returns_422(
    mock_service: AsyncMock, mock_sfn: MagicMock
) -> None:
    # Arrange
    app.dependency_overrides[get_admin_key] = _bypass_admin_key
    app.dependency_overrides[get_scraping_job_service] = lambda: mock_service
    app.dependency_overrides[get_sfn_client] = lambda: mock_sfn

    # Act
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/admin/scraping-jobs",
            json={"category": "restaurants"},
        )

    # Assert
    assert response.status_code == 422


async def test_create_job_without_admin_key_returns_401() -> None:
    # Arrange — no override for get_admin_key; send wrong key
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/admin/scraping-jobs",
            json={"category": "restaurants", "zone": "CABA"},
            headers={"X-Admin-Key": "wrong-key"},
        )

    # Assert
    assert response.status_code == 401
    assert response.json() == {"error": "Invalid or missing admin key"}


async def test_create_job_without_admin_key_header_returns_422() -> None:
    # Arrange — no X-Admin-Key header at all (FastAPI returns 422 for missing required header)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/admin/scraping-jobs",
            json={"category": "restaurants", "zone": "CABA"},
        )

    # Assert
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /admin/scraping-jobs
# ---------------------------------------------------------------------------


async def test_list_jobs_returns_200(mock_service: AsyncMock) -> None:
    # Arrange
    app.dependency_overrides[get_admin_key] = _bypass_admin_key
    app.dependency_overrides[get_scraping_job_service] = lambda: mock_service

    # Act
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/admin/scraping-jobs")

    # Assert
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert len(body) == 1
    assert body[0]["category"] == "restaurants"


async def test_list_jobs_passes_status_filter(mock_service: AsyncMock) -> None:
    # Arrange
    app.dependency_overrides[get_admin_key] = _bypass_admin_key
    app.dependency_overrides[get_scraping_job_service] = lambda: mock_service
    mock_service.list_jobs.return_value = []

    # Act
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/admin/scraping-jobs?status=pending")

    # Assert
    assert response.status_code == 200
    mock_service.list_jobs.assert_called_once_with(status="pending")


# ---------------------------------------------------------------------------
# GET /admin/scraping-jobs/{job_id}
# ---------------------------------------------------------------------------


async def test_get_job_returns_200_when_found(mock_service: AsyncMock) -> None:
    # Arrange
    app.dependency_overrides[get_admin_key] = _bypass_admin_key
    app.dependency_overrides[get_scraping_job_service] = lambda: mock_service

    # Act
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/admin/scraping-jobs/{_SAMPLE_RESPONSE.id}")

    # Assert
    assert response.status_code == 200
    assert response.json()["id"] == _SAMPLE_RESPONSE.id


async def test_get_job_returns_404_when_not_found(mock_service: AsyncMock) -> None:
    # Arrange
    app.dependency_overrides[get_admin_key] = _bypass_admin_key
    app.dependency_overrides[get_scraping_job_service] = lambda: mock_service
    mock_service.get_job.return_value = None

    # Act
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/admin/scraping-jobs/non-existent-id")

    # Assert
    assert response.status_code == 404
    assert response.json() == {"error": "Scraping job not found"}


# ---------------------------------------------------------------------------
# SFN execution trigger
# ---------------------------------------------------------------------------


async def test_create_job_starts_sfn_execution(mock_service: AsyncMock) -> None:
    # Arrange
    mock_sfn = MagicMock()
    mock_sfn.start_execution = MagicMock()
    app.dependency_overrides[get_admin_key] = _bypass_admin_key
    app.dependency_overrides[get_scraping_job_service] = lambda: mock_service
    app.dependency_overrides[get_sfn_client] = lambda: mock_sfn

    # Act
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/admin/scraping-jobs",
            json={"category": "restaurants", "zone": "CABA"},
        )

    # Assert
    assert response.status_code == 202
    mock_sfn.start_execution.assert_called_once_with(_SAMPLE_RESPONSE.id)
