"""Tests for OrderService admin methods: list_all_orders, download_order (SCRUM-42/22)."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.services.order_service import OrderService
from app.domain.models.order import Order
from app.infrastructure.aws.s3_client import IS3Client

_NOW = datetime(2026, 3, 8, tzinfo=UTC)
_USER_ID = "550e8400-e29b-41d4-a716-446655440001"
_OTHER_USER_ID = "550e8400-e29b-41d4-a716-446655440099"
_ORDER_ID = "550e8400-e29b-41d4-a716-446655440020"


def _make_order(
    status: str = "completed",
    result_path: str | None = "results/order-20.csv",
    user_id: str = _USER_ID,
) -> Order:
    return Order(
        id=_ORDER_ID,
        user_id=user_id,
        offer_id="offer-1",
        zone="CABA",
        format="csv",
        status=status,
        total_usd=Decimal("29.99"),
        stripe_payment_intent_id="pi_test",
        scraping_job_id=None,
        result_path=result_path,
        created_at=_NOW,
        paid_at=_NOW if status != "pending" else None,
        completed_at=_NOW if status == "completed" else None,
    )


@pytest.fixture
def mock_order_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.find_all.return_value = [_make_order(), _make_order(status="pending", result_path=None)]
    repo.find_by_id.return_value = _make_order()
    return repo


@pytest.fixture
def mock_s3() -> MagicMock:
    client = MagicMock(spec=IS3Client)
    client.get_object_bytes.return_value = b"col1,col2\nval1,val2"
    return client


@pytest.fixture
def service(mock_order_repo: AsyncMock, mock_s3: MagicMock) -> OrderService:
    return OrderService(
        order_repository=mock_order_repo,
        offer_repository=AsyncMock(),
        pricing_repository=AsyncMock(),
        stripe_client=MagicMock(),
        s3_client=mock_s3,
    )


# ---------------------------------------------------------------------------
# list_all_orders (SCRUM-42)
# ---------------------------------------------------------------------------


async def test_list_all_orders_returns_all(
    service: OrderService, mock_order_repo: AsyncMock
) -> None:
    result = await service.list_all_orders()

    mock_order_repo.find_all.assert_called_once_with(None)
    assert len(result) == 2


async def test_list_all_orders_with_status_filter(
    service: OrderService, mock_order_repo: AsyncMock
) -> None:
    mock_order_repo.find_all.return_value = [_make_order()]

    result = await service.list_all_orders("completed")

    mock_order_repo.find_all.assert_called_once_with("completed")
    assert len(result) == 1
    assert result[0].status == "completed"


# ---------------------------------------------------------------------------
# download_order (SCRUM-22)
# ---------------------------------------------------------------------------


async def test_download_order_returns_bytes_and_format(
    service: OrderService, mock_s3: MagicMock
) -> None:
    data, fmt = await service.download_order(_ORDER_ID, _USER_ID)

    assert data == b"col1,col2\nval1,val2"
    assert fmt == "csv"
    mock_s3.get_object_bytes.assert_called_once_with("results/order-20.csv")


async def test_download_order_raises_404_when_not_found(
    service: OrderService, mock_order_repo: AsyncMock
) -> None:
    mock_order_repo.find_by_id.return_value = None

    with pytest.raises(Exception) as exc_info:
        await service.download_order("nonexistent", _USER_ID)

    assert exc_info.value.status_code == 404  # type: ignore[attr-defined]


async def test_download_order_raises_403_for_wrong_user(
    service: OrderService, mock_order_repo: AsyncMock
) -> None:
    mock_order_repo.find_by_id.return_value = _make_order(user_id=_OTHER_USER_ID)

    with pytest.raises(Exception) as exc_info:
        await service.download_order(_ORDER_ID, _USER_ID)

    assert exc_info.value.status_code == 403  # type: ignore[attr-defined]


async def test_download_order_raises_404_when_not_completed(
    service: OrderService, mock_order_repo: AsyncMock
) -> None:
    mock_order_repo.find_by_id.return_value = _make_order(status="paid", result_path=None)

    with pytest.raises(Exception) as exc_info:
        await service.download_order(_ORDER_ID, _USER_ID)

    assert exc_info.value.status_code == 404  # type: ignore[attr-defined]
