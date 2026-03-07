from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from app.application.services.offer_service import OfferService
from app.domain.models.offer import Offer
from app.presentation.schemas.offer_schemas import CreateOfferRequest, UpdateOfferRequest

_NOW = datetime(2025, 1, 1, tzinfo=UTC)
_OFFER_ID = "550e8400-e29b-41d4-a716-446655440010"


def _make_offer(**kwargs: object) -> Offer:
    defaults = {
        "id": _OFFER_ID,
        "title": "Restaurantes",
        "category": "restaurants",
        "description": "Desc.",
        "is_active": False,
        "created_at": _NOW,
        "updated_at": _NOW,
    }
    defaults.update(kwargs)
    return Offer(**defaults)  # type: ignore[arg-type]


@pytest.fixture
def mock_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def service(mock_repo: AsyncMock) -> OfferService:
    return OfferService(mock_repo)


# ---------------------------------------------------------------------------
# create_offer
# ---------------------------------------------------------------------------


async def test_create_offer_saves_and_returns_response(
    service: OfferService, mock_repo: AsyncMock
) -> None:
    mock_repo.find_by_category.return_value = None
    mock_repo.save.return_value = None
    payload = CreateOfferRequest(title="Restaurantes", category="restaurants")

    result = await service.create_offer(payload)

    assert result.title == "Restaurantes"
    assert result.category == "restaurants"
    assert result.is_active is False
    mock_repo.save.assert_called_once()


async def test_create_offer_generates_unique_ids(
    service: OfferService, mock_repo: AsyncMock
) -> None:
    mock_repo.find_by_category.return_value = None
    mock_repo.save.return_value = None
    payload = CreateOfferRequest(title="Restaurantes", category="restaurants")

    r1 = await service.create_offer(payload)
    r2 = await service.create_offer(payload)

    assert r1.id != r2.id


async def test_create_offer_raises_409_if_category_exists(
    service: OfferService, mock_repo: AsyncMock
) -> None:
    mock_repo.find_by_category.return_value = _make_offer()
    payload = CreateOfferRequest(title="Otro título", category="restaurants")

    with pytest.raises(Exception) as exc_info:
        await service.create_offer(payload)

    assert exc_info.value.status_code == 409  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# update_offer
# ---------------------------------------------------------------------------


async def test_update_offer_returns_updated_response(
    service: OfferService, mock_repo: AsyncMock
) -> None:
    mock_repo.find_by_id.return_value = _make_offer()
    mock_repo.update.return_value = None
    payload = UpdateOfferRequest(title="Nuevo título", is_active=True)

    result = await service.update_offer(_OFFER_ID, payload)

    assert result.title == "Nuevo título"
    assert result.is_active is True
    mock_repo.update.assert_called_once()


async def test_update_offer_partial_patch_preserves_other_fields(
    service: OfferService, mock_repo: AsyncMock
) -> None:
    mock_repo.find_by_id.return_value = _make_offer(description="Original desc")
    mock_repo.update.return_value = None
    payload = UpdateOfferRequest(is_active=True)

    result = await service.update_offer(_OFFER_ID, payload)

    assert result.description == "Original desc"
    assert result.is_active is True


async def test_update_offer_raises_404_when_not_found(
    service: OfferService, mock_repo: AsyncMock
) -> None:
    mock_repo.find_by_id.return_value = None
    payload = UpdateOfferRequest(title="X")

    with pytest.raises(Exception) as exc_info:
        await service.update_offer("non-existent-id", payload)

    assert exc_info.value.status_code == 404  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# delete_offer
# ---------------------------------------------------------------------------


async def test_delete_offer_calls_repository_delete(
    service: OfferService, mock_repo: AsyncMock
) -> None:
    mock_repo.find_by_id.return_value = _make_offer()
    mock_repo.has_orders.return_value = False
    mock_repo.delete.return_value = None

    await service.delete_offer(_OFFER_ID)

    mock_repo.delete.assert_called_once_with(_OFFER_ID)


async def test_delete_offer_raises_404_when_not_found(
    service: OfferService, mock_repo: AsyncMock
) -> None:
    mock_repo.find_by_id.return_value = None

    with pytest.raises(Exception) as exc_info:
        await service.delete_offer("non-existent-id")

    assert exc_info.value.status_code == 404  # type: ignore[attr-defined]


async def test_delete_offer_raises_409_when_has_orders(
    service: OfferService, mock_repo: AsyncMock
) -> None:
    mock_repo.find_by_id.return_value = _make_offer()
    mock_repo.has_orders.return_value = True

    with pytest.raises(Exception) as exc_info:
        await service.delete_offer(_OFFER_ID)

    assert exc_info.value.status_code == 409  # type: ignore[attr-defined]
    mock_repo.delete.assert_not_called()
