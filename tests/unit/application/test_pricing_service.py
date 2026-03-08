"""Tests for PricingService (SCRUM-41)."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from app.application.services.pricing_service import PricingService
from app.domain.models.pricing import Pricing
from app.presentation.schemas.pricing_schemas import UpsertPricingEntry, UpsertPricingRequest

_NOW = datetime(2026, 3, 8, tzinfo=UTC)


def _make_pricing(zone: str = "CABA", price: str = "29.99") -> Pricing:
    return Pricing(
        id="p-1",
        zone=zone,
        price_usd=Decimal(price),
        created_at=_NOW,
        updated_at=_NOW,
    )


@pytest.fixture
def mock_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.find_all.return_value = [_make_pricing("CABA", "29.99"), _make_pricing("Buenos Aires", "19.99")]
    repo.upsert.return_value = _make_pricing()
    return repo


@pytest.fixture
def service(mock_repo: AsyncMock) -> PricingService:
    return PricingService(mock_repo)


async def test_list_pricing_returns_all_entries(service: PricingService, mock_repo: AsyncMock) -> None:
    result = await service.list_pricing()

    assert len(result) == 2
    assert result[0].zone == "CABA"
    assert result[0].price_usd == 29.99
    mock_repo.find_all.assert_called_once()


async def test_list_pricing_returns_empty_when_no_entries(
    service: PricingService, mock_repo: AsyncMock
) -> None:
    mock_repo.find_all.return_value = []

    result = await service.list_pricing()

    assert result == []


async def test_upsert_pricing_calls_repo_for_each_entry(
    service: PricingService, mock_repo: AsyncMock
) -> None:
    payload = UpsertPricingRequest(
        entries=[
            UpsertPricingEntry(zone="CABA", price_usd=29.99),
            UpsertPricingEntry(zone="Buenos Aires", price_usd=19.99),
        ]
    )

    result = await service.upsert_pricing(payload)

    assert mock_repo.upsert.call_count == 2
    assert len(result) == 2


async def test_upsert_pricing_passes_correct_args(
    service: PricingService, mock_repo: AsyncMock
) -> None:
    payload = UpsertPricingRequest(
        entries=[UpsertPricingEntry(zone="CABA", price_usd=29.99)]
    )

    await service.upsert_pricing(payload)

    mock_repo.upsert.assert_called_once_with("CABA", "29.99")


async def test_upsert_pricing_returns_updated_entries(
    service: PricingService, mock_repo: AsyncMock
) -> None:
    mock_repo.upsert.return_value = _make_pricing("CABA", "35.00")
    payload = UpsertPricingRequest(
        entries=[UpsertPricingEntry(zone="CABA", price_usd=35.0)]
    )

    result = await service.upsert_pricing(payload)

    assert result[0].price_usd == 35.0
