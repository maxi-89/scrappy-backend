from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.domain.models.business import Business

_NOW = datetime(2025, 1, 1, tzinfo=UTC)
_JOB_ID = "550e8400-e29b-41d4-a716-446655440000"
_BIZ_ID = "660e8400-e29b-41d4-a716-446655440001"


def _valid_business(**overrides: object) -> Business:
    defaults: dict[str, object] = {
        "id": _BIZ_ID,
        "scraping_job_id": _JOB_ID,
        "name": "El Cuartito",
        "category": "restaurants",
        "zone": "CABA",
        "address": "Talcahuano 937, Buenos Aires",
        "phone": "+54 11 4816-1758",
        "website": "https://elcuartito.com.ar",
        "google_maps_url": "https://maps.google.com/?cid=123",
        "rating": Decimal("4.5"),
        "review_count": 1200,
        "latitude": Decimal("-34.5997"),
        "longitude": Decimal("-58.3819"),
        "is_verified": False,
        "scraped_at": _NOW,
        "created_at": _NOW,
    }
    defaults.update(overrides)
    return Business(**defaults)  # type: ignore[arg-type]


def test_valid_business_created_successfully() -> None:
    # Arrange / Act
    biz = _valid_business()

    # Assert
    assert biz.id == _BIZ_ID
    assert biz.scraping_job_id == _JOB_ID
    assert biz.name == "El Cuartito"
    assert biz.category == "restaurants"
    assert biz.zone == "CABA"
    assert biz.rating == Decimal("4.5")
    assert biz.review_count == 1200
    assert biz.is_verified is False


def test_empty_name_raises_value_error() -> None:
    with pytest.raises(ValueError, match="name"):
        _valid_business(name="")


def test_whitespace_only_name_raises_value_error() -> None:
    with pytest.raises(ValueError, match="name"):
        _valid_business(name="   ")


def test_empty_category_raises_value_error() -> None:
    with pytest.raises(ValueError, match="category"):
        _valid_business(category="")


def test_empty_zone_raises_value_error() -> None:
    with pytest.raises(ValueError, match="zone"):
        _valid_business(zone="")


def test_empty_scraping_job_id_raises_value_error() -> None:
    with pytest.raises(ValueError, match="scraping_job_id"):
        _valid_business(scraping_job_id="")


def test_whitespace_only_scraping_job_id_raises_value_error() -> None:
    with pytest.raises(ValueError, match="scraping_job_id"):
        _valid_business(scraping_job_id="   ")


def test_rating_above_5_raises_value_error() -> None:
    with pytest.raises(ValueError, match="rating"):
        _valid_business(rating=Decimal("5.1"))


def test_rating_below_0_raises_value_error() -> None:
    with pytest.raises(ValueError, match="rating"):
        _valid_business(rating=Decimal("-0.1"))


def test_rating_exactly_5_is_valid() -> None:
    biz = _valid_business(rating=Decimal("5.0"))
    assert biz.rating == Decimal("5.0")


def test_rating_exactly_0_is_valid() -> None:
    biz = _valid_business(rating=Decimal("0.0"))
    assert biz.rating == Decimal("0.0")


def test_rating_none_is_valid() -> None:
    biz = _valid_business(rating=None)
    assert biz.rating is None


def test_negative_review_count_raises_value_error() -> None:
    with pytest.raises(ValueError, match="review_count"):
        _valid_business(review_count=-1)


def test_zero_review_count_is_valid() -> None:
    biz = _valid_business(review_count=0)
    assert biz.review_count == 0


def test_all_optional_fields_can_be_none() -> None:
    biz = _valid_business(
        address=None,
        phone=None,
        website=None,
        google_maps_url=None,
        rating=None,
        latitude=None,
        longitude=None,
    )
    assert biz.address is None
    assert biz.phone is None
    assert biz.website is None
    assert biz.google_maps_url is None
    assert biz.rating is None
    assert biz.latitude is None
    assert biz.longitude is None
