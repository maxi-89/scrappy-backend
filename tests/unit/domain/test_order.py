from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.domain.models.order import Order

_NOW = datetime(2025, 1, 1, tzinfo=UTC)
_ORDER_ID = "550e8400-e29b-41d4-a716-446655440020"
_USER_ID = "550e8400-e29b-41d4-a716-446655440001"
_OFFER_ID = "550e8400-e29b-41d4-a716-446655440010"

_VALID_FORMATS = ["csv", "excel", "json"]
_VALID_STATUSES = ["pending", "paid", "scraping", "completed", "failed", "refunded"]


def _make_order(**kwargs: object) -> Order:
    defaults = {
        "id": _ORDER_ID,
        "user_id": _USER_ID,
        "offer_id": _OFFER_ID,
        "zone": "CABA",
        "format": "csv",
        "status": "pending",
        "total_usd": Decimal("29.99"),
        "stripe_payment_intent_id": None,
        "scraping_job_id": None,
        "result_path": None,
        "created_at": _NOW,
        "paid_at": None,
        "completed_at": None,
    }
    defaults.update(kwargs)
    return Order(**defaults)  # type: ignore[arg-type]


def test_order_created_successfully() -> None:
    order = _make_order()
    assert order.id == _ORDER_ID
    assert order.status == "pending"
    assert order.total_usd == Decimal("29.99")


@pytest.mark.parametrize("fmt", _VALID_FORMATS)
def test_order_accepts_valid_formats(fmt: str) -> None:
    order = _make_order(format=fmt)
    assert order.format == fmt


@pytest.mark.parametrize("status", _VALID_STATUSES)
def test_order_accepts_valid_statuses(status: str) -> None:
    order = _make_order(status=status)
    assert order.status == status


def test_order_raises_if_format_invalid() -> None:
    with pytest.raises(ValueError, match="format"):
        _make_order(format="xml")


def test_order_raises_if_status_invalid() -> None:
    with pytest.raises(ValueError, match="status"):
        _make_order(status="unknown")


def test_order_raises_if_zone_empty() -> None:
    with pytest.raises(ValueError, match="zone"):
        _make_order(zone="")


def test_order_raises_if_total_usd_negative() -> None:
    with pytest.raises(ValueError, match="total_usd"):
        _make_order(total_usd=Decimal("-1.00"))
