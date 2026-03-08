"""Tests for GET /orders and GET /orders/{id} (SCRUM-20 and SCRUM-21)."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.domain.models.current_user import CurrentUser
from app.infrastructure.dependencies import get_current_user, get_order_service
from app.infrastructure.errors.app_error import AppError
from app.presentation.schemas.order_schemas import OrderDetailResponse, OrderResponse, ScrapingJobSchema
from main import app

_USER_ID = "550e8400-e29b-41d4-a716-446655440001"
_OTHER_USER_ID = "550e8400-e29b-41d4-a716-446655440099"
_ORDER_ID = "550e8400-e29b-41d4-a716-446655440020"
_JOB_ID = "550e8400-e29b-41d4-a716-446655440030"

_NOW = datetime(2026, 3, 8, 12, 0, 0, tzinfo=UTC)

_CURRENT_USER = CurrentUser(sub="auth0|test", email="buyer@test.com", user_id=_USER_ID)

_SAMPLE_JOB = ScrapingJobSchema(
    id=_JOB_ID,
    category="restaurants",
    zone="CABA",
    status="completed",
    records_scraped=150,
    error_message=None,
    started_at=_NOW,
    finished_at=_NOW,
    created_at=_NOW,
)

_SAMPLE_ORDER_RESPONSE = OrderResponse(
    id=_ORDER_ID,
    offer_id="offer-123",
    zone="CABA",
    format="csv",
    status="completed",
    total_usd=29.99,
    created_at=_NOW,
    paid_at=_NOW,
    completed_at=_NOW,
)

_SAMPLE_ORDER_DETAIL = OrderDetailResponse(
    id=_ORDER_ID,
    offer_id="offer-123",
    zone="CABA",
    format="csv",
    status="completed",
    total_usd=29.99,
    created_at=_NOW,
    paid_at=_NOW,
    completed_at=_NOW,
    scraping_job=_SAMPLE_JOB,
)


@pytest.fixture(autouse=True)
def clear_overrides() -> None:  # type: ignore[misc]
    yield
    app.dependency_overrides.clear()


def _bypass_auth() -> CurrentUser:
    return _CURRENT_USER


@pytest.fixture
def mock_service() -> AsyncMock:
    svc = AsyncMock()
    svc.list_orders.return_value = [_SAMPLE_ORDER_RESPONSE]
    svc.get_order.return_value = _SAMPLE_ORDER_DETAIL
    return svc


# ---------------------------------------------------------------------------
# GET /orders  (SCRUM-20)
# ---------------------------------------------------------------------------


async def test_list_orders_returns_200(mock_service: AsyncMock) -> None:
    app.dependency_overrides[get_current_user] = _bypass_auth
    app.dependency_overrides[get_order_service] = lambda: mock_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/orders")

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert len(body) == 1
    assert body[0]["id"] == _ORDER_ID


async def test_list_orders_passes_user_id_to_service(mock_service: AsyncMock) -> None:
    app.dependency_overrides[get_current_user] = _bypass_auth
    app.dependency_overrides[get_order_service] = lambda: mock_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.get("/orders")

    mock_service.list_orders.assert_called_once_with(_USER_ID)


async def test_list_orders_returns_empty_list_when_no_orders(mock_service: AsyncMock) -> None:
    app.dependency_overrides[get_current_user] = _bypass_auth
    app.dependency_overrides[get_order_service] = lambda: mock_service
    mock_service.list_orders.return_value = []

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/orders")

    assert response.status_code == 200
    assert response.json() == []


async def test_list_orders_unauthenticated_returns_401() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/orders")

    assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /orders/{id}  (SCRUM-21)
# ---------------------------------------------------------------------------


async def test_get_order_returns_200(mock_service: AsyncMock) -> None:
    app.dependency_overrides[get_current_user] = _bypass_auth
    app.dependency_overrides[get_order_service] = lambda: mock_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/orders/{_ORDER_ID}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == _ORDER_ID
    assert body["scraping_job"]["id"] == _JOB_ID


async def test_get_order_passes_order_id_and_user_id_to_service(mock_service: AsyncMock) -> None:
    app.dependency_overrides[get_current_user] = _bypass_auth
    app.dependency_overrides[get_order_service] = lambda: mock_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.get(f"/orders/{_ORDER_ID}")

    mock_service.get_order.assert_called_once_with(_ORDER_ID, _USER_ID)


async def test_get_order_not_found_returns_404(mock_service: AsyncMock) -> None:
    app.dependency_overrides[get_current_user] = _bypass_auth
    app.dependency_overrides[get_order_service] = lambda: mock_service
    mock_service.get_order.side_effect = AppError("Order not found", status_code=404)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/orders/nonexistent")

    assert response.status_code == 404


async def test_get_order_wrong_user_returns_403(mock_service: AsyncMock) -> None:
    app.dependency_overrides[get_current_user] = _bypass_auth
    app.dependency_overrides[get_order_service] = lambda: mock_service
    mock_service.get_order.side_effect = AppError("Access denied", status_code=403)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/orders/{_ORDER_ID}")

    assert response.status_code == 403


async def test_get_order_no_scraping_job_returns_null(mock_service: AsyncMock) -> None:
    app.dependency_overrides[get_current_user] = _bypass_auth
    app.dependency_overrides[get_order_service] = lambda: mock_service
    mock_service.get_order.return_value = OrderDetailResponse(
        id=_ORDER_ID,
        offer_id="offer-123",
        zone="CABA",
        format="csv",
        status="pending",
        total_usd=29.99,
        created_at=_NOW,
        paid_at=None,
        completed_at=None,
        scraping_job=None,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/orders/{_ORDER_ID}")

    assert response.status_code == 200
    assert response.json()["scraping_job"] is None


async def test_get_order_unauthenticated_returns_401() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/orders/{_ORDER_ID}")

    assert response.status_code == 401
