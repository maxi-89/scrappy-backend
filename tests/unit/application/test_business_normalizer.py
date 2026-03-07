from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.application.workers.business_normalizer import BusinessNormalizer
from app.domain.models.business import Business

_NOW = datetime(2025, 1, 1, tzinfo=UTC)
_JOB_ID = "550e8400-e29b-41d4-a716-446655440000"


def _make_business(**kwargs: object) -> Business:
    defaults: dict[str, object] = {
        "id": "biz-1",
        "scraping_job_id": _JOB_ID,
        "name": "El Cuartito",
        "category": "restaurants",
        "zone": "CABA",
        "address": "Talcahuano 937",
        "phone": None,
        "website": None,
        "google_maps_url": None,
        "rating": Decimal("4.5"),
        "review_count": 100,
        "latitude": Decimal("34.6037"),
        "longitude": Decimal("-58.3816"),
        "is_verified": False,
        "scraped_at": _NOW,
        "created_at": _NOW,
    }
    defaults.update(kwargs)
    return Business(**defaults)  # type: ignore[arg-type]


@pytest.fixture
def normalizer() -> BusinessNormalizer:
    return BusinessNormalizer()


# ---------------------------------------------------------------------------
# Whitespace trimming
# ---------------------------------------------------------------------------


def test_trims_whitespace_from_name(normalizer: BusinessNormalizer) -> None:
    biz = _make_business(name="  El Cuartito  ")
    result = normalizer.normalize([biz])
    assert result[0].name == "El Cuartito"


def test_trims_whitespace_from_address(normalizer: BusinessNormalizer) -> None:
    biz = _make_business(address="  Talcahuano 937  ")
    result = normalizer.normalize([biz])
    assert result[0].address == "Talcahuano 937"


def test_trims_whitespace_from_phone(normalizer: BusinessNormalizer) -> None:
    biz = _make_business(phone="  +54 11 1234 5678  ")
    result = normalizer.normalize([biz])
    assert result[0].phone == "+54 11 1234 5678"


def test_none_fields_remain_none(normalizer: BusinessNormalizer) -> None:
    biz = _make_business(phone=None, address=None, website=None)
    result = normalizer.normalize([biz])
    assert result[0].phone is None
    assert result[0].address is None
    assert result[0].website is None


# ---------------------------------------------------------------------------
# Phone normalization
# ---------------------------------------------------------------------------


def test_removes_dashes_from_phone(normalizer: BusinessNormalizer) -> None:
    biz = _make_business(phone="011-4123-4567")
    result = normalizer.normalize([biz])
    assert "-" not in result[0].phone  # type: ignore[operator]


def test_preserves_plus_prefix_in_phone(normalizer: BusinessNormalizer) -> None:
    biz = _make_business(phone="+54-11-4123-4567")
    result = normalizer.normalize([biz])
    assert result[0].phone is not None
    assert result[0].phone.startswith("+")


# ---------------------------------------------------------------------------
# Category normalization
# ---------------------------------------------------------------------------


def test_lowercases_category(normalizer: BusinessNormalizer) -> None:
    biz = _make_business(category="Restaurants")
    result = normalizer.normalize([biz])
    assert result[0].category == "restaurants"


def test_strips_category(normalizer: BusinessNormalizer) -> None:
    biz = _make_business(category="  restaurants  ")
    result = normalizer.normalize([biz])
    assert result[0].category == "restaurants"


# ---------------------------------------------------------------------------
# Deduplication by (name, address)
# ---------------------------------------------------------------------------


def test_deduplicates_exact_name_and_address(normalizer: BusinessNormalizer) -> None:
    biz1 = _make_business(id="biz-1", name="El Cuartito", address="Talcahuano 937")
    biz2 = _make_business(id="biz-2", name="El Cuartito", address="Talcahuano 937")
    result = normalizer.normalize([biz1, biz2])
    assert len(result) == 1
    assert result[0].id == "biz-1"


def test_deduplication_is_case_insensitive_on_name(normalizer: BusinessNormalizer) -> None:
    biz1 = _make_business(id="biz-1", name="El Cuartito", address="Talcahuano 937")
    biz2 = _make_business(id="biz-2", name="el cuartito", address="Talcahuano 937")
    result = normalizer.normalize([biz1, biz2])
    assert len(result) == 1


def test_keeps_distinct_businesses(normalizer: BusinessNormalizer) -> None:
    biz1 = _make_business(id="biz-1", name="El Cuartito", address="Talcahuano 937")
    biz2 = _make_business(id="biz-2", name="La Americana", address="Callao 83")
    result = normalizer.normalize([biz1, biz2])
    assert len(result) == 2


def test_deduplicates_when_address_is_none(normalizer: BusinessNormalizer) -> None:
    biz1 = _make_business(id="biz-1", name="El Cuartito", address=None)
    biz2 = _make_business(id="biz-2", name="El Cuartito", address=None)
    result = normalizer.normalize([biz1, biz2])
    assert len(result) == 1


def test_empty_list_returns_empty(normalizer: BusinessNormalizer) -> None:
    result = normalizer.normalize([])
    assert result == []
