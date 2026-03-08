"""Tests for OrderService.list_orders and OrderService.get_order (SCRUM-20/21)."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.services.order_service import OrderService
from app.domain.models.order import Order
from app.domain.models.scraping_job import ScrapingJob

_NOW = datetime(2026, 3, 8, tzinfo=UTC)
_USER_ID = "550e8400-e29b-41d4-a716-446655440001"
_OTHER_USER_ID = "550e8400-e29b-41d4-a716-446655440099"
_ORDER_ID = "550e8400-e29b-41d4-a716-446655440020"
_JOB_ID = "550e8400-e29b-41d4-a716-446655440030"


def _make_order(user_id: str = _USER_ID, scraping_job_id: str | None = _JOB_ID) -> Order:
    return Order(
        id=_ORDER_ID,
        user_id=user_id,
        offer_id="offer-123",
        zone="CABA",
        format="csv",
        status="completed",
        total_usd=Decimal("29.99"),
        stripe_payment_intent_id="pi_test_123",
        scraping_job_id=scraping_job_id,
        result_path=None,
        created_at=_NOW,
        paid_at=_NOW,
        completed_at=_NOW,
    )


def _make_scraping_job() -> ScrapingJob:
    return ScrapingJob(
        id=_JOB_ID,
        category="restaurants",
        zone="CABA",
        status="completed",
        order_id=_ORDER_ID,
        records_scraped=150,
        error_message=None,
        started_at=_NOW,
        finished_at=_NOW,
        created_at=_NOW,
    )


@pytest.fixture
def mock_order_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.find_by_user.return_value = [_make_order()]
    repo.find_by_id.return_value = _make_order()
    return repo


@pytest.fixture
def mock_scraping_job_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.find_by_id.return_value = _make_scraping_job()
    return repo


@pytest.fixture
def service(mock_order_repo: AsyncMock, mock_scraping_job_repo: AsyncMock) -> OrderService:
    return OrderService(
        order_repository=mock_order_repo,
        offer_repository=AsyncMock(),
        pricing_repository=AsyncMock(),
        stripe_client=MagicMock(),
        scraping_job_repository=mock_scraping_job_repo,
    )


# ---------------------------------------------------------------------------
# list_orders
# ---------------------------------------------------------------------------


async def test_list_orders_returns_orders_for_user(
    service: OrderService, mock_order_repo: AsyncMock
) -> None:
    result = await service.list_orders(_USER_ID)

    assert len(result) == 1
    assert result[0].id == _ORDER_ID
    mock_order_repo.find_by_user.assert_called_once_with(_USER_ID)


async def test_list_orders_returns_empty_when_none(
    service: OrderService, mock_order_repo: AsyncMock
) -> None:
    mock_order_repo.find_by_user.return_value = []

    result = await service.list_orders(_USER_ID)

    assert result == []


# ---------------------------------------------------------------------------
# get_order
# ---------------------------------------------------------------------------


async def test_get_order_returns_detail_with_scraping_job(
    service: OrderService, mock_order_repo: AsyncMock, mock_scraping_job_repo: AsyncMock
) -> None:
    result = await service.get_order(_ORDER_ID, _USER_ID)

    assert result.id == _ORDER_ID
    assert result.scraping_job is not None
    assert result.scraping_job.id == _JOB_ID
    mock_scraping_job_repo.find_by_id.assert_called_once_with(_JOB_ID)


async def test_get_order_returns_null_scraping_job_when_not_linked(
    service: OrderService, mock_order_repo: AsyncMock
) -> None:
    mock_order_repo.find_by_id.return_value = _make_order(scraping_job_id=None)

    result = await service.get_order(_ORDER_ID, _USER_ID)

    assert result.scraping_job is None


async def test_get_order_raises_404_when_not_found(
    service: OrderService, mock_order_repo: AsyncMock
) -> None:
    mock_order_repo.find_by_id.return_value = None

    with pytest.raises(Exception) as exc_info:
        await service.get_order("nonexistent", _USER_ID)

    assert exc_info.value.status_code == 404  # type: ignore[attr-defined]


async def test_get_order_raises_403_when_wrong_user(
    service: OrderService, mock_order_repo: AsyncMock
) -> None:
    mock_order_repo.find_by_id.return_value = _make_order(user_id=_OTHER_USER_ID)

    with pytest.raises(Exception) as exc_info:
        await service.get_order(_ORDER_ID, _USER_ID)

    assert exc_info.value.status_code == 403  # type: ignore[attr-defined]
