from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.infrastructure.dependencies import get_admin_key, get_offer_service
from app.infrastructure.errors.app_error import AppError
from app.presentation.schemas.offer_schemas import OfferResponse
from main import app

_NOW = datetime(2025, 1, 1, tzinfo=UTC)
_OFFER_ID = "550e8400-e29b-41d4-a716-446655440010"

_SAMPLE_RESPONSE = OfferResponse(
    id=_OFFER_ID,
    title="Restaurantes",
    category="restaurants",
    description="Desc.",
    is_active=False,
    created_at=_NOW,
    updated_at=_NOW,
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
    svc.create_offer.return_value = _SAMPLE_RESPONSE
    svc.update_offer.return_value = _SAMPLE_RESPONSE
    svc.delete_offer.return_value = None
    return svc


# ---------------------------------------------------------------------------
# POST /admin/offers
# ---------------------------------------------------------------------------


async def test_create_offer_returns_201(mock_service: AsyncMock) -> None:
    app.dependency_overrides[get_admin_key] = _bypass_admin_key
    app.dependency_overrides[get_offer_service] = lambda: mock_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/admin/offers",
            json={"title": "Restaurantes", "category": "restaurants"},
        )

    assert response.status_code == 201
    body = response.json()
    assert body["category"] == "restaurants"
    assert body["title"] == "Restaurantes"
    mock_service.create_offer.assert_called_once()


async def test_create_offer_missing_title_returns_422(mock_service: AsyncMock) -> None:
    app.dependency_overrides[get_admin_key] = _bypass_admin_key
    app.dependency_overrides[get_offer_service] = lambda: mock_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/admin/offers", json={"category": "restaurants"})

    assert response.status_code == 422


async def test_create_offer_duplicate_category_returns_409(mock_service: AsyncMock) -> None:
    app.dependency_overrides[get_admin_key] = _bypass_admin_key
    app.dependency_overrides[get_offer_service] = lambda: mock_service
    mock_service.create_offer.side_effect = AppError("already exists", status_code=409)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/admin/offers",
            json={"title": "Otro", "category": "restaurants"},
        )

    assert response.status_code == 409


async def test_create_offer_without_admin_key_returns_422() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/admin/offers",
            json={"title": "Restaurantes", "category": "restaurants"},
        )

    assert response.status_code == 422


async def test_create_offer_wrong_admin_key_returns_401() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/admin/offers",
            json={"title": "Restaurantes", "category": "restaurants"},
            headers={"X-Admin-Key": "wrong-key"},
        )

    assert response.status_code == 401


# ---------------------------------------------------------------------------
# PATCH /admin/offers/{offer_id}
# ---------------------------------------------------------------------------


async def test_update_offer_returns_200(mock_service: AsyncMock) -> None:
    app.dependency_overrides[get_admin_key] = _bypass_admin_key
    app.dependency_overrides[get_offer_service] = lambda: mock_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.patch(
            f"/admin/offers/{_OFFER_ID}",
            json={"title": "Nuevo título", "is_active": True},
        )

    assert response.status_code == 200
    mock_service.update_offer.assert_called_once()


async def test_update_offer_not_found_returns_404(mock_service: AsyncMock) -> None:
    app.dependency_overrides[get_admin_key] = _bypass_admin_key
    app.dependency_overrides[get_offer_service] = lambda: mock_service
    mock_service.update_offer.side_effect = AppError("Offer not found", status_code=404)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.patch(
            "/admin/offers/non-existent-id",
            json={"is_active": True},
        )

    assert response.status_code == 404
    assert response.json() == {"error": "Offer not found"}


# ---------------------------------------------------------------------------
# DELETE /admin/offers/{offer_id}
# ---------------------------------------------------------------------------


async def test_delete_offer_returns_204(mock_service: AsyncMock) -> None:
    app.dependency_overrides[get_admin_key] = _bypass_admin_key
    app.dependency_overrides[get_offer_service] = lambda: mock_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.delete(f"/admin/offers/{_OFFER_ID}")

    assert response.status_code == 204
    mock_service.delete_offer.assert_called_once_with(_OFFER_ID)


async def test_delete_offer_not_found_returns_404(mock_service: AsyncMock) -> None:
    app.dependency_overrides[get_admin_key] = _bypass_admin_key
    app.dependency_overrides[get_offer_service] = lambda: mock_service
    mock_service.delete_offer.side_effect = AppError("Offer not found", status_code=404)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.delete("/admin/offers/non-existent-id")

    assert response.status_code == 404


async def test_delete_offer_with_orders_returns_409(mock_service: AsyncMock) -> None:
    app.dependency_overrides[get_admin_key] = _bypass_admin_key
    app.dependency_overrides[get_offer_service] = lambda: mock_service
    mock_service.delete_offer.side_effect = AppError(
        "Cannot delete offer with associated orders", status_code=409
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.delete(f"/admin/offers/{_OFFER_ID}")

    assert response.status_code == 409
