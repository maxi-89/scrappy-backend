"""Tests for GET /admin/orders (SCRUM-42)."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.infrastructure.dependencies import get_admin_key, get_order_service
from app.presentation.schemas.order_schemas import OrderDetailResponse
from main import app

_NOW = datetime(2026, 3, 8, 12, 0, 0, tzinfo=UTC)

_ORDER_1 = OrderDetailResponse(
    id="order-1",
    offer_id="offer-1",
    zone="CABA",
    format="csv",
    status="completed",
    total_usd=29.99,
    created_at=_NOW,
    paid_at=_NOW,
    completed_at=_NOW,
    scraping_job=None,
)
_ORDER_2 = OrderDetailResponse(
    id="order-2",
    offer_id="offer-1",
    zone="Buenos Aires",
    format="json",
    status="pending",
    total_usd=19.99,
    created_at=_NOW,
    paid_at=None,
    completed_at=None,
    scraping_job=None,
)


def _bypass_admin_key() -> str:
    return "test-admin-key"


@pytest.fixture(autouse=True)
def clear_overrides() -> None:  # type: ignore[misc]
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def mock_service() -> AsyncMock:
    svc = AsyncMock()
    svc.list_all_orders_detailed.return_value = [_ORDER_1, _ORDER_2]
    return svc


# ---------------------------------------------------------------------------
# GET /admin/orders
# ---------------------------------------------------------------------------


async def test_list_all_orders_returns_200(mock_service: AsyncMock) -> None:
    app.dependency_overrides[get_admin_key] = _bypass_admin_key
    app.dependency_overrides[get_order_service] = lambda: mock_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/admin/orders")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert body[0]["id"] == "order-1"
    assert "scraping_job" in body[0]


async def test_list_all_orders_no_filter_calls_service_with_none(mock_service: AsyncMock) -> None:
    app.dependency_overrides[get_admin_key] = _bypass_admin_key
    app.dependency_overrides[get_order_service] = lambda: mock_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.get("/admin/orders")

    mock_service.list_all_orders_detailed.assert_called_once_with(None)


async def test_list_all_orders_with_status_filter(mock_service: AsyncMock) -> None:
    app.dependency_overrides[get_admin_key] = _bypass_admin_key
    app.dependency_overrides[get_order_service] = lambda: mock_service
    mock_service.list_all_orders_detailed.return_value = [_ORDER_2]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/admin/orders?status=pending")

    assert response.status_code == 200
    mock_service.list_all_orders_detailed.assert_called_once_with("pending")


async def test_list_all_orders_returns_empty_list(mock_service: AsyncMock) -> None:
    app.dependency_overrides[get_admin_key] = _bypass_admin_key
    app.dependency_overrides[get_order_service] = lambda: mock_service
    mock_service.list_all_orders_detailed.return_value = []

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/admin/orders")

    assert response.status_code == 200
    assert response.json() == []


async def test_list_all_orders_missing_admin_key_returns_422(mock_service: AsyncMock) -> None:
    app.dependency_overrides[get_order_service] = lambda: mock_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/admin/orders")

    assert response.status_code == 422


async def test_list_all_orders_wrong_admin_key_returns_401(mock_service: AsyncMock) -> None:
    app.dependency_overrides[get_order_service] = lambda: mock_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/admin/orders", headers={"x-admin-key": "wrong"})

    assert response.status_code == 401
