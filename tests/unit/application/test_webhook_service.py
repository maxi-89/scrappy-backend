"""Tests for StripeWebhookService (SCRUM-19)."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.services.webhook_service import StripeWebhookService
from app.domain.models.offer import Offer
from app.domain.models.order import Order

_NOW = datetime(2025, 1, 1, tzinfo=UTC)
_ORDER_ID = "550e8400-e29b-41d4-a716-446655440020"
_OFFER_ID = "550e8400-e29b-41d4-a716-446655440010"
_USER_ID = "550e8400-e29b-41d4-a716-446655440001"
_PI_ID = "pi_test_123"
_WEBHOOK_SECRET = "whsec_test"


def _make_order(**kwargs: object) -> Order:
    defaults: dict[str, object] = {
        "id": _ORDER_ID,
        "user_id": _USER_ID,
        "offer_id": _OFFER_ID,
        "zone": "CABA",
        "format": "csv",
        "status": "pending",
        "total_usd": Decimal("29.99"),
        "stripe_payment_intent_id": _PI_ID,
        "scraping_job_id": None,
        "result_path": None,
        "created_at": _NOW,
        "paid_at": None,
        "completed_at": None,
    }
    defaults.update(kwargs)
    return Order(**defaults)  # type: ignore[arg-type]


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


def _payment_succeeded_event(pi_id: str = _PI_ID) -> dict:  # type: ignore[type-arg]
    return {
        "type": "payment_intent.succeeded",
        "data": {"object": {"id": pi_id}},
    }


@pytest.fixture
def mock_stripe() -> MagicMock:
    client = MagicMock()
    client.construct_event.return_value = _payment_succeeded_event()
    return client


@pytest.fixture
def mock_order_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.find_by_stripe_payment_intent_id.return_value = _make_order()
    repo.update.return_value = None
    return repo


@pytest.fixture
def mock_offer_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.find_by_id.return_value = _make_offer()
    return repo


@pytest.fixture
def mock_scraping_job_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.save.return_value = None
    return repo


@pytest.fixture
def mock_sfn() -> MagicMock:
    sfn = MagicMock()
    sfn.start_execution = MagicMock()
    return sfn


@pytest.fixture
def service(
    mock_stripe: MagicMock,
    mock_order_repo: AsyncMock,
    mock_offer_repo: AsyncMock,
    mock_scraping_job_repo: AsyncMock,
    mock_sfn: MagicMock,
) -> StripeWebhookService:
    return StripeWebhookService(
        stripe_client=mock_stripe,
        order_repository=mock_order_repo,
        offer_repository=mock_offer_repo,
        scraping_job_repository=mock_scraping_job_repo,
        sfn_client=mock_sfn,
        webhook_secret=_WEBHOOK_SECRET,
    )


# ---------------------------------------------------------------------------
# handle_event
# ---------------------------------------------------------------------------


async def test_payment_succeeded_marks_order_as_paid(
    service: StripeWebhookService, mock_order_repo: AsyncMock
) -> None:
    await service.handle_event(b"payload", "sig")

    updated_order = mock_order_repo.update.call_args[0][0]
    assert updated_order.status == "paid"
    assert updated_order.paid_at is not None


async def test_payment_succeeded_creates_scraping_job(
    service: StripeWebhookService, mock_scraping_job_repo: AsyncMock
) -> None:
    await service.handle_event(b"payload", "sig")

    mock_scraping_job_repo.save.assert_called_once()
    saved_job = mock_scraping_job_repo.save.call_args[0][0]
    assert saved_job.category == "restaurants"
    assert saved_job.zone == "CABA"
    assert saved_job.order_id == _ORDER_ID
    assert saved_job.status == "pending"


async def test_payment_succeeded_triggers_sfn(
    service: StripeWebhookService, mock_sfn: MagicMock
) -> None:
    await service.handle_event(b"payload", "sig")

    mock_sfn.start_execution.assert_called_once()


async def test_payment_succeeded_updates_order_with_scraping_job_id(
    service: StripeWebhookService, mock_order_repo: AsyncMock
) -> None:
    await service.handle_event(b"payload", "sig")

    # update is called twice: once to mark paid, once to set scraping_job_id
    assert mock_order_repo.update.call_count == 2
    final_order = mock_order_repo.update.call_args_list[1][0][0]
    assert final_order.scraping_job_id is not None


async def test_unknown_event_type_is_ignored(
    service: StripeWebhookService,
    mock_stripe: MagicMock,
    mock_order_repo: AsyncMock,
) -> None:
    mock_stripe.construct_event.return_value = {
        "type": "customer.created",
        "data": {"object": {}},
    }

    await service.handle_event(b"payload", "sig")

    mock_order_repo.update.assert_not_called()


async def test_order_not_found_is_handled_gracefully(
    service: StripeWebhookService,
    mock_order_repo: AsyncMock,
    mock_scraping_job_repo: AsyncMock,
) -> None:
    mock_order_repo.find_by_stripe_payment_intent_id.return_value = None

    # Should not raise; idempotent
    await service.handle_event(b"payload", "sig")

    mock_order_repo.update.assert_not_called()
    mock_scraping_job_repo.save.assert_not_called()


async def test_already_paid_order_is_skipped(
    service: StripeWebhookService,
    mock_order_repo: AsyncMock,
    mock_scraping_job_repo: AsyncMock,
) -> None:
    mock_order_repo.find_by_stripe_payment_intent_id.return_value = _make_order(status="paid")

    await service.handle_event(b"payload", "sig")

    mock_order_repo.update.assert_not_called()
    mock_scraping_job_repo.save.assert_not_called()


async def test_invalid_signature_raises_400(
    service: StripeWebhookService, mock_stripe: MagicMock
) -> None:
    import stripe as stripe_lib

    mock_stripe.construct_event.side_effect = stripe_lib.error.SignatureVerificationError(
        "bad sig", "sig"
    )

    with pytest.raises(Exception) as exc_info:
        await service.handle_event(b"payload", "bad-sig")

    assert exc_info.value.status_code == 400  # type: ignore[attr-defined]
