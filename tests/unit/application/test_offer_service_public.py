"""Tests for public offer listing (SCRUM-16/17)."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from app.application.services.offer_service import OfferService
from app.domain.models.offer import Offer
from app.domain.models.pricing import Pricing

_NOW = datetime(2025, 1, 1, tzinfo=UTC)
_OFFER_ID = "550e8400-e29b-41d4-a716-446655440010"


def _make_offer(**kwargs: object) -> Offer:
    defaults = {
        "id": _OFFER_ID,
        "title": "Restaurantes",
        "category": "restaurants",
        "description": "Desc.",
        "is_active": True,
        "created_at": _NOW,
        "updated_at": _NOW,
    }
    defaults.update(kwargs)
    return Offer(**defaults)  # type: ignore[arg-type]


def _make_pricing(zone: str = "CABA", price: str = "29.99") -> Pricing:
    return Pricing(
        id="pricing-1",
        zone=zone,
        price_usd=Decimal(price),
        created_at=_NOW,
        updated_at=_NOW,
    )


@pytest.fixture
def mock_offer_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_pricing_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def service(mock_offer_repo: AsyncMock, mock_pricing_repo: AsyncMock) -> OfferService:
    return OfferService(mock_offer_repo, mock_pricing_repo)


# ---------------------------------------------------------------------------
# list_active_offers
# ---------------------------------------------------------------------------


async def test_list_active_offers_returns_all_active(
    service: OfferService, mock_offer_repo: AsyncMock
) -> None:
    mock_offer_repo.find_all_active.return_value = [_make_offer()]

    result = await service.list_active_offers(zone=None)

    assert len(result) == 1
    assert result[0].category == "restaurants"
    assert result[0].price_usd is None
    mock_offer_repo.find_all_active.assert_called_once()


async def test_list_active_offers_with_zone_includes_price(
    service: OfferService, mock_offer_repo: AsyncMock, mock_pricing_repo: AsyncMock
) -> None:
    mock_offer_repo.find_all_active.return_value = [_make_offer()]
    mock_pricing_repo.find_by_zone.return_value = _make_pricing(zone="CABA", price="29.99")

    result = await service.list_active_offers(zone="CABA")

    assert result[0].price_usd == 29.99
    mock_pricing_repo.find_by_zone.assert_called_once_with("CABA")


async def test_list_active_offers_with_unknown_zone_returns_none_price(
    service: OfferService, mock_offer_repo: AsyncMock, mock_pricing_repo: AsyncMock
) -> None:
    mock_offer_repo.find_all_active.return_value = [_make_offer()]
    mock_pricing_repo.find_by_zone.return_value = None

    result = await service.list_active_offers(zone="unknown-zone")

    assert result[0].price_usd is None


async def test_list_active_offers_empty_returns_empty(
    service: OfferService, mock_offer_repo: AsyncMock
) -> None:
    mock_offer_repo.find_all_active.return_value = []

    result = await service.list_active_offers(zone=None)

    assert result == []


# ---------------------------------------------------------------------------
# get_active_offer
# ---------------------------------------------------------------------------


async def test_get_active_offer_returns_response_when_found(
    service: OfferService, mock_offer_repo: AsyncMock, mock_pricing_repo: AsyncMock
) -> None:
    mock_offer_repo.find_active_by_id.return_value = _make_offer()
    mock_pricing_repo.find_by_zone.return_value = _make_pricing()

    result = await service.get_active_offer(_OFFER_ID, zone="CABA")

    assert result is not None
    assert result.id == _OFFER_ID
    assert result.price_usd == 29.99


async def test_get_active_offer_without_zone_omits_price(
    service: OfferService, mock_offer_repo: AsyncMock, mock_pricing_repo: AsyncMock
) -> None:
    mock_offer_repo.find_active_by_id.return_value = _make_offer()

    result = await service.get_active_offer(_OFFER_ID, zone=None)

    assert result is not None
    assert result.price_usd is None
    mock_pricing_repo.find_by_zone.assert_not_called()


async def test_get_active_offer_returns_none_when_not_found(
    service: OfferService, mock_offer_repo: AsyncMock
) -> None:
    mock_offer_repo.find_active_by_id.return_value = None

    result = await service.get_active_offer("non-existent", zone=None)

    assert result is None
