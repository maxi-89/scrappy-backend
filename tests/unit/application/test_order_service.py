from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.services.order_service import OrderService
from app.domain.models.offer import Offer
from app.domain.models.pricing import Pricing
from app.infrastructure.stripe.stripe_client import PaymentIntentResult
from app.presentation.schemas.order_schemas import CreateOrderRequest

_NOW = datetime(2025, 1, 1, tzinfo=UTC)
_USER_ID = "550e8400-e29b-41d4-a716-446655440001"
_OFFER_ID = "550e8400-e29b-41d4-a716-446655440010"
_ORDER_ID = "550e8400-e29b-41d4-a716-446655440020"


def _make_offer() -> Offer:
    return Offer(
        id=_OFFER_ID,
        title="Restaurantes",
        category="restaurants",
        description="Desc.",
        is_active=True,
        created_at=_NOW,
        updated_at=_NOW,
    )


def _make_pricing() -> Pricing:
    return Pricing(
        id="pricing-1",
        zone="CABA",
        price_usd=Decimal("29.99"),
        created_at=_NOW,
        updated_at=_NOW,
    )


def _make_payment_intent() -> PaymentIntentResult:
    return PaymentIntentResult(
        payment_intent_id="pi_test_123",
        client_secret="pi_test_123_secret_abc",
    )


@pytest.fixture
def mock_order_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_offer_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.find_active_by_id.return_value = _make_offer()
    return repo


@pytest.fixture
def mock_pricing_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.find_by_zone.return_value = _make_pricing()
    return repo


@pytest.fixture
def mock_stripe() -> MagicMock:
    client = MagicMock()
    client.create_payment_intent.return_value = _make_payment_intent()
    return client


@pytest.fixture
def service(
    mock_order_repo: AsyncMock,
    mock_offer_repo: AsyncMock,
    mock_pricing_repo: AsyncMock,
    mock_stripe: MagicMock,
) -> OrderService:
    return OrderService(mock_order_repo, mock_offer_repo, mock_pricing_repo, mock_stripe)


# ---------------------------------------------------------------------------
# create_order
# ---------------------------------------------------------------------------


async def test_create_order_returns_response_with_client_secret(
    service: OrderService, mock_order_repo: AsyncMock
) -> None:
    payload = CreateOrderRequest(offer_id=_OFFER_ID, zone="CABA", format="csv")

    result = await service.create_order(_USER_ID, payload)

    assert result.client_secret == "pi_test_123_secret_abc"
    assert result.total_usd == 29.99
    assert result.order_id is not None
    mock_order_repo.save.assert_called_once()


async def test_create_order_saves_with_pending_status(
    service: OrderService, mock_order_repo: AsyncMock
) -> None:
    payload = CreateOrderRequest(offer_id=_OFFER_ID, zone="CABA", format="csv")

    await service.create_order(_USER_ID, payload)

    saved_order = mock_order_repo.save.call_args[0][0]
    assert saved_order.status == "pending"
    assert saved_order.user_id == _USER_ID
    assert saved_order.offer_id == _OFFER_ID
    assert saved_order.stripe_payment_intent_id == "pi_test_123"


async def test_create_order_raises_404_if_offer_not_found(
    service: OrderService, mock_offer_repo: AsyncMock
) -> None:
    mock_offer_repo.find_active_by_id.return_value = None
    payload = CreateOrderRequest(offer_id="non-existent", zone="CABA", format="csv")

    with pytest.raises(Exception) as exc_info:
        await service.create_order(_USER_ID, payload)

    assert exc_info.value.status_code == 404  # type: ignore[attr-defined]


async def test_create_order_raises_404_if_zone_has_no_pricing(
    service: OrderService, mock_pricing_repo: AsyncMock
) -> None:
    mock_pricing_repo.find_by_zone.return_value = None
    payload = CreateOrderRequest(offer_id=_OFFER_ID, zone="unknown-zone", format="csv")

    with pytest.raises(Exception) as exc_info:
        await service.create_order(_USER_ID, payload)

    assert exc_info.value.status_code == 404  # type: ignore[attr-defined]


async def test_create_order_calls_stripe_with_correct_amount(
    service: OrderService, mock_stripe: MagicMock
) -> None:
    payload = CreateOrderRequest(offer_id=_OFFER_ID, zone="CABA", format="csv")

    await service.create_order(_USER_ID, payload)

    mock_stripe.create_payment_intent.assert_called_once()
    call_args = mock_stripe.create_payment_intent.call_args
    assert call_args[1]["amount_usd"] == 29.99 or call_args[0][0] == 29.99
