from datetime import UTC, datetime

import pytest

from app.domain.models.offer import Offer

_NOW = datetime(2025, 1, 1, tzinfo=UTC)
_OFFER_ID = "550e8400-e29b-41d4-a716-446655440010"


def _make_offer(**kwargs: object) -> Offer:
    defaults = {
        "id": _OFFER_ID,
        "title": "Restaurantes",
        "category": "restaurants",
        "description": "Listado de restaurantes.",
        "is_active": False,
        "created_at": _NOW,
        "updated_at": _NOW,
    }
    defaults.update(kwargs)
    return Offer(**defaults)  # type: ignore[arg-type]


def test_offer_created_successfully() -> None:
    offer = _make_offer()
    assert offer.id == _OFFER_ID
    assert offer.title == "Restaurantes"
    assert offer.category == "restaurants"
    assert offer.is_active is False


def test_offer_with_no_description() -> None:
    offer = _make_offer(description=None)
    assert offer.description is None


def test_offer_raises_if_title_is_empty() -> None:
    with pytest.raises(ValueError, match="title"):
        _make_offer(title="")


def test_offer_raises_if_title_is_whitespace() -> None:
    with pytest.raises(ValueError, match="title"):
        _make_offer(title="   ")


def test_offer_raises_if_category_is_empty() -> None:
    with pytest.raises(ValueError, match="category"):
        _make_offer(category="")


def test_offer_raises_if_category_is_whitespace() -> None:
    with pytest.raises(ValueError, match="category"):
        _make_offer(category="   ")
