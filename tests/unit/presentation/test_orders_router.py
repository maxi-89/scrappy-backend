from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.infrastructure.dependencies import get_current_user, get_order_service
from app.infrastructure.errors.app_error import AppError
from app.domain.models.current_user import CurrentUser
from app.presentation.schemas.order_schemas import CreateOrderResponse
from main import app

_USER_ID = "550e8400-e29b-41d4-a716-446655440001"
_ORDER_ID = "550e8400-e29b-41d4-a716-446655440020"

_SAMPLE_RESPONSE = CreateOrderResponse(
    order_id=_ORDER_ID,
    client_secret="pi_test_123_secret_abc",
    total_usd=29.99,
)

_CURRENT_USER = CurrentUser(sub="auth0|test123", email="buyer@test.com", user_id=_USER_ID)


@pytest.fixture(autouse=True)
def clear_overrides() -> None:  # type: ignore[misc]
    yield
    app.dependency_overrides.clear()


def _bypass_auth() -> CurrentUser:
    return _CURRENT_USER


@pytest.fixture
def mock_service() -> AsyncMock:
    svc = AsyncMock()
    svc.create_order.return_value = _SAMPLE_RESPONSE
    return svc


# ---------------------------------------------------------------------------
# POST /orders
# ---------------------------------------------------------------------------


async def test_create_order_returns_201(mock_service: AsyncMock) -> None:
    app.dependency_overrides[get_current_user] = _bypass_auth
    app.dependency_overrides[get_order_service] = lambda: mock_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/orders",
            json={"offer_id": "some-offer-id", "zone": "CABA", "format": "csv"},
        )

    assert response.status_code == 201
    body = response.json()
    assert body["order_id"] == _ORDER_ID
    assert body["client_secret"] == "pi_test_123_secret_abc"
    assert body["total_usd"] == 29.99
    mock_service.create_order.assert_called_once()


async def test_create_order_passes_user_id_to_service(mock_service: AsyncMock) -> None:
    app.dependency_overrides[get_current_user] = _bypass_auth
    app.dependency_overrides[get_order_service] = lambda: mock_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/orders",
            json={"offer_id": "some-offer-id", "zone": "CABA", "format": "csv"},
        )

    call_args = mock_service.create_order.call_args
    assert call_args[0][0] == _USER_ID


async def test_create_order_missing_format_returns_422(mock_service: AsyncMock) -> None:
    app.dependency_overrides[get_current_user] = _bypass_auth
    app.dependency_overrides[get_order_service] = lambda: mock_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/orders",
            json={"offer_id": "some-offer-id", "zone": "CABA"},
        )

    assert response.status_code == 422


async def test_create_order_invalid_format_returns_422(mock_service: AsyncMock) -> None:
    app.dependency_overrides[get_current_user] = _bypass_auth
    app.dependency_overrides[get_order_service] = lambda: mock_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/orders",
            json={"offer_id": "some-offer-id", "zone": "CABA", "format": "xml"},
        )

    assert response.status_code == 422


async def test_create_order_offer_not_found_returns_404(mock_service: AsyncMock) -> None:
    app.dependency_overrides[get_current_user] = _bypass_auth
    app.dependency_overrides[get_order_service] = lambda: mock_service
    mock_service.create_order.side_effect = AppError("Offer not found", status_code=404)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/orders",
            json={"offer_id": "bad-id", "zone": "CABA", "format": "csv"},
        )

    assert response.status_code == 404


async def test_create_order_unauthenticated_returns_401() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/orders",
            json={"offer_id": "some-offer-id", "zone": "CABA", "format": "csv"},
        )

    assert response.status_code == 401
