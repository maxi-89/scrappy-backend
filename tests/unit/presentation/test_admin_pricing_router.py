"""Tests for GET/PUT /admin/pricing (SCRUM-41)."""

from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.infrastructure.dependencies import get_admin_key, get_pricing_service
from app.presentation.schemas.pricing_schemas import PricingEntryResponse
from main import app

_ENTRY_1 = PricingEntryResponse(id="p-1", zone="CABA", price_usd=29.99)
_ENTRY_2 = PricingEntryResponse(id="p-2", zone="Buenos Aires", price_usd=19.99)


def _bypass_admin_key() -> str:
    return "test-admin-key"


@pytest.fixture(autouse=True)
def clear_overrides() -> None:  # type: ignore[misc]
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def mock_service() -> AsyncMock:
    svc = AsyncMock()
    svc.list_pricing.return_value = [_ENTRY_1, _ENTRY_2]
    svc.upsert_pricing.return_value = [_ENTRY_1]
    return svc


# ---------------------------------------------------------------------------
# GET /admin/pricing
# ---------------------------------------------------------------------------


async def test_list_pricing_returns_200(mock_service: AsyncMock) -> None:
    app.dependency_overrides[get_admin_key] = _bypass_admin_key
    app.dependency_overrides[get_pricing_service] = lambda: mock_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/admin/pricing")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert body[0]["zone"] == "CABA"
    assert body[0]["price_usd"] == 29.99


async def test_list_pricing_returns_empty_list(mock_service: AsyncMock) -> None:
    app.dependency_overrides[get_admin_key] = _bypass_admin_key
    app.dependency_overrides[get_pricing_service] = lambda: mock_service
    mock_service.list_pricing.return_value = []

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/admin/pricing")

    assert response.status_code == 200
    assert response.json() == []


async def test_list_pricing_missing_admin_key_returns_422(mock_service: AsyncMock) -> None:
    app.dependency_overrides[get_pricing_service] = lambda: mock_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/admin/pricing")

    assert response.status_code == 422


async def test_list_pricing_wrong_admin_key_returns_401(mock_service: AsyncMock) -> None:
    app.dependency_overrides[get_pricing_service] = lambda: mock_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/admin/pricing", headers={"x-admin-key": "wrong"})

    assert response.status_code == 401


# ---------------------------------------------------------------------------
# PUT /admin/pricing
# ---------------------------------------------------------------------------


async def test_upsert_pricing_returns_200(mock_service: AsyncMock) -> None:
    app.dependency_overrides[get_admin_key] = _bypass_admin_key
    app.dependency_overrides[get_pricing_service] = lambda: mock_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.put(
            "/admin/pricing",
            json={"entries": [{"zone": "CABA", "price_usd": 29.99}]},
        )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["zone"] == "CABA"


async def test_upsert_pricing_calls_service(mock_service: AsyncMock) -> None:
    app.dependency_overrides[get_admin_key] = _bypass_admin_key
    app.dependency_overrides[get_pricing_service] = lambda: mock_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.put(
            "/admin/pricing",
            json={"entries": [{"zone": "CABA", "price_usd": 29.99}]},
        )

    mock_service.upsert_pricing.assert_called_once()


async def test_upsert_pricing_empty_entries_returns_422(mock_service: AsyncMock) -> None:
    app.dependency_overrides[get_admin_key] = _bypass_admin_key
    app.dependency_overrides[get_pricing_service] = lambda: mock_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.put("/admin/pricing", json={"entries": []})

    assert response.status_code == 422


async def test_upsert_pricing_negative_price_returns_422(mock_service: AsyncMock) -> None:
    app.dependency_overrides[get_admin_key] = _bypass_admin_key
    app.dependency_overrides[get_pricing_service] = lambda: mock_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.put(
            "/admin/pricing",
            json={"entries": [{"zone": "CABA", "price_usd": -1}]},
        )

    assert response.status_code == 422


async def test_upsert_pricing_missing_admin_key_returns_422(mock_service: AsyncMock) -> None:
    app.dependency_overrides[get_pricing_service] = lambda: mock_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.put(
            "/admin/pricing",
            json={"entries": [{"zone": "CABA", "price_usd": 29.99}]},
        )

    assert response.status_code == 422


async def test_upsert_pricing_wrong_admin_key_returns_401(mock_service: AsyncMock) -> None:
    app.dependency_overrides[get_pricing_service] = lambda: mock_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.put(
            "/admin/pricing",
            headers={"x-admin-key": "wrong"},
            json={"entries": [{"zone": "CABA", "price_usd": 29.99}]},
        )

    assert response.status_code == 401
