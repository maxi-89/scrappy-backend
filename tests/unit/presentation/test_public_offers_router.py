from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.infrastructure.dependencies import get_offer_service
from app.presentation.schemas.offer_schemas import PublicOfferResponse
from main import app

_OFFER_ID = "550e8400-e29b-41d4-a716-446655440010"

_SAMPLE = PublicOfferResponse(
    id=_OFFER_ID,
    title="Restaurantes",
    category="restaurants",
    description="Desc.",
    is_active=True,
    price_usd=None,
)

_SAMPLE_WITH_PRICE = PublicOfferResponse(
    id=_OFFER_ID,
    title="Restaurantes",
    category="restaurants",
    description="Desc.",
    is_active=True,
    price_usd=29.99,
)


@pytest.fixture(autouse=True)
def clear_overrides() -> None:  # type: ignore[misc]
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def mock_service() -> AsyncMock:
    svc = AsyncMock()
    svc.list_active_offers.return_value = [_SAMPLE]
    svc.get_active_offer.return_value = _SAMPLE
    return svc


# ---------------------------------------------------------------------------
# GET /offers
# ---------------------------------------------------------------------------


async def test_list_offers_returns_200(mock_service: AsyncMock) -> None:
    app.dependency_overrides[get_offer_service] = lambda: mock_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/offers")

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert body[0]["category"] == "restaurants"
    assert body[0]["price_usd"] is None
    mock_service.list_active_offers.assert_called_once_with(zone=None)


async def test_list_offers_with_zone_passes_zone_to_service(mock_service: AsyncMock) -> None:
    app.dependency_overrides[get_offer_service] = lambda: mock_service
    mock_service.list_active_offers.return_value = [_SAMPLE_WITH_PRICE]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/offers?zone=CABA")

    assert response.status_code == 200
    mock_service.list_active_offers.assert_called_once_with(zone="CABA")
    assert response.json()[0]["price_usd"] == 29.99


async def test_list_offers_no_auth_required(mock_service: AsyncMock) -> None:
    app.dependency_overrides[get_offer_service] = lambda: mock_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/offers")

    assert response.status_code == 200


# ---------------------------------------------------------------------------
# GET /offers/{offer_id}
# ---------------------------------------------------------------------------


async def test_get_offer_returns_200_when_found(mock_service: AsyncMock) -> None:
    app.dependency_overrides[get_offer_service] = lambda: mock_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/offers/{_OFFER_ID}")

    assert response.status_code == 200
    assert response.json()["id"] == _OFFER_ID
    mock_service.get_active_offer.assert_called_once_with(_OFFER_ID, zone=None)


async def test_get_offer_with_zone_passes_zone_to_service(mock_service: AsyncMock) -> None:
    app.dependency_overrides[get_offer_service] = lambda: mock_service
    mock_service.get_active_offer.return_value = _SAMPLE_WITH_PRICE

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/offers/{_OFFER_ID}?zone=CABA")

    assert response.status_code == 200
    mock_service.get_active_offer.assert_called_once_with(_OFFER_ID, zone="CABA")
    assert response.json()["price_usd"] == 29.99


async def test_get_offer_returns_404_when_not_found(mock_service: AsyncMock) -> None:
    app.dependency_overrides[get_offer_service] = lambda: mock_service
    mock_service.get_active_offer.return_value = None

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/offers/non-existent-id")

    assert response.status_code == 404
    assert response.json() == {"error": "Offer not found"}
