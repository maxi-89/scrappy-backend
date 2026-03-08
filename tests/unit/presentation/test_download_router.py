"""Tests for GET /orders/{id}/download (SCRUM-22)."""

from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.domain.models.current_user import CurrentUser
from app.infrastructure.dependencies import get_current_user, get_order_service
from app.infrastructure.errors.app_error import AppError
from main import app

_USER_ID = "550e8400-e29b-41d4-a716-446655440001"
_ORDER_ID = "550e8400-e29b-41d4-a716-446655440020"
_CURRENT_USER = CurrentUser(sub="auth0|test", email="buyer@test.com", user_id=_USER_ID)


@pytest.fixture(autouse=True)
def clear_overrides() -> None:  # type: ignore[misc]
    yield
    app.dependency_overrides.clear()


def _bypass_auth() -> CurrentUser:
    return _CURRENT_USER


@pytest.fixture
def mock_service() -> AsyncMock:
    svc = AsyncMock()
    svc.download_order.return_value = (b"col1,col2\nval1,val2", "csv")
    return svc


# ---------------------------------------------------------------------------
# GET /orders/{id}/download
# ---------------------------------------------------------------------------


async def test_download_order_returns_200_with_csv(mock_service: AsyncMock) -> None:
    app.dependency_overrides[get_current_user] = _bypass_auth
    app.dependency_overrides[get_order_service] = lambda: mock_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/orders/{_ORDER_ID}/download")

    assert response.status_code == 200
    assert response.content == b"col1,col2\nval1,val2"
    assert "text/csv" in response.headers["content-type"]


async def test_download_order_returns_json_content_type_for_json_format(
    mock_service: AsyncMock,
) -> None:
    app.dependency_overrides[get_current_user] = _bypass_auth
    app.dependency_overrides[get_order_service] = lambda: mock_service
    mock_service.download_order.return_value = (b'[{"name":"test"}]', "json")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/orders/{_ORDER_ID}/download")

    assert response.status_code == 200
    assert "application/json" in response.headers["content-type"]


async def test_download_order_passes_order_id_and_user_id(mock_service: AsyncMock) -> None:
    app.dependency_overrides[get_current_user] = _bypass_auth
    app.dependency_overrides[get_order_service] = lambda: mock_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.get(f"/orders/{_ORDER_ID}/download")

    mock_service.download_order.assert_called_once_with(_ORDER_ID, _USER_ID)


async def test_download_order_not_found_returns_404(mock_service: AsyncMock) -> None:
    app.dependency_overrides[get_current_user] = _bypass_auth
    app.dependency_overrides[get_order_service] = lambda: mock_service
    mock_service.download_order.side_effect = AppError("Order not found", status_code=404)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/orders/nonexistent/download")

    assert response.status_code == 404


async def test_download_order_wrong_user_returns_403(mock_service: AsyncMock) -> None:
    app.dependency_overrides[get_current_user] = _bypass_auth
    app.dependency_overrides[get_order_service] = lambda: mock_service
    mock_service.download_order.side_effect = AppError("Access denied", status_code=403)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/orders/{_ORDER_ID}/download")

    assert response.status_code == 403


async def test_download_order_not_completed_returns_404(mock_service: AsyncMock) -> None:
    app.dependency_overrides[get_current_user] = _bypass_auth
    app.dependency_overrides[get_order_service] = lambda: mock_service
    mock_service.download_order.side_effect = AppError("Result not available yet", status_code=404)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/orders/{_ORDER_ID}/download")

    assert response.status_code == 404


async def test_download_order_unauthenticated_returns_401() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/orders/{_ORDER_ID}/download")

    assert response.status_code == 401
