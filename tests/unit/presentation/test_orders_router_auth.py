from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.domain.models.current_user import CurrentUser
from app.infrastructure.dependencies import get_current_user, get_user_service
from main import app

_VALID_USER = CurrentUser(sub="auth0|123", email="u@test.com")


def _mock_user_service() -> MagicMock:
    svc = MagicMock()
    svc.sync_user = AsyncMock(return_value=None)
    return svc


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> None:  # type: ignore[misc]
    yield
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Unauthenticated requests — no Authorization header
# ---------------------------------------------------------------------------


async def test_get_orders_returns_401_when_no_authorization_header() -> None:
    # Arrange / Act
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/orders")

    # Assert
    assert response.status_code == 401
    assert response.json() == {"error": "Missing authentication token"}


async def test_post_orders_returns_401_when_no_authorization_header() -> None:
    # Arrange / Act
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/orders", json={})

    # Assert
    assert response.status_code == 401
    assert response.json() == {"error": "Missing authentication token"}


async def test_get_order_by_id_returns_401_when_no_authorization_header() -> None:
    # Arrange / Act
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/orders/some-id")

    # Assert
    assert response.status_code == 401
    assert response.json() == {"error": "Missing authentication token"}


async def test_download_order_returns_401_when_no_authorization_header() -> None:
    # Arrange / Act
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/orders/some-order/download")

    # Assert
    assert response.status_code == 401
    assert response.json() == {"error": "Missing authentication token"}


# ---------------------------------------------------------------------------
# Invalid token
# ---------------------------------------------------------------------------


async def test_get_orders_returns_401_when_token_is_invalid() -> None:
    # Arrange
    app.dependency_overrides[get_user_service] = _mock_user_service
    with (
        patch("app.infrastructure.auth.auth0_jwt_verifier._get_jwks_client") as mock_client,
        patch("app.infrastructure.auth.auth0_jwt_verifier.jwt.decode") as mock_decode,
    ):
        from jwt import InvalidTokenError

        mock_client.return_value.get_signing_key_from_jwt.return_value = MagicMock(key="k")
        mock_decode.side_effect = InvalidTokenError("bad")

        # Act
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/orders", headers={"Authorization": "Bearer bad.token.here"}
            )

    # Assert
    assert response.status_code == 401
    assert response.json() == {"error": "Invalid authentication token"}


async def test_get_orders_returns_401_when_token_is_expired() -> None:
    # Arrange
    app.dependency_overrides[get_user_service] = _mock_user_service
    with (
        patch("app.infrastructure.auth.auth0_jwt_verifier._get_jwks_client") as mock_client,
        patch("app.infrastructure.auth.auth0_jwt_verifier.jwt.decode") as mock_decode,
    ):
        from jwt import ExpiredSignatureError

        mock_client.return_value.get_signing_key_from_jwt.return_value = MagicMock(key="k")
        mock_decode.side_effect = ExpiredSignatureError("expired")

        # Act
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/orders", headers={"Authorization": "Bearer expired.token.here"}
            )

    # Assert
    assert response.status_code == 401
    assert response.json() == {"error": "Authentication token expired"}


# ---------------------------------------------------------------------------
# Authenticated requests — override get_current_user
# ---------------------------------------------------------------------------


async def test_authenticated_get_orders_returns_200() -> None:
    # Arrange — bypass real JWT verification and order service
    from app.infrastructure.dependencies import get_order_service

    mock_svc = AsyncMock()
    mock_svc.list_orders.return_value = []
    app.dependency_overrides[get_current_user] = lambda: _VALID_USER
    app.dependency_overrides[get_order_service] = lambda: mock_svc

    # Act
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/orders", headers={"Authorization": "Bearer fake"})

    # Assert — endpoint is now implemented
    assert response.status_code == 200
    assert response.json() == []


async def test_authenticated_post_orders_missing_body_returns_422() -> None:
    # Arrange — POST /orders is now a real endpoint; empty body → validation error
    app.dependency_overrides[get_current_user] = lambda: _VALID_USER

    # Act
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/orders", json={}, headers={"Authorization": "Bearer fake"})

    # Assert
    assert response.status_code == 422


async def test_authenticated_get_order_by_id_returns_404_when_not_found() -> None:
    # Arrange
    from app.infrastructure.dependencies import get_order_service
    from app.infrastructure.errors.app_error import AppError

    mock_svc = AsyncMock()
    mock_svc.get_order.side_effect = AppError("Order not found", status_code=404)
    app.dependency_overrides[get_current_user] = lambda: _VALID_USER
    app.dependency_overrides[get_order_service] = lambda: mock_svc

    # Act
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/orders/some-order-id", headers={"Authorization": "Bearer fake"}
        )

    # Assert — endpoint is now implemented, 404 for missing order
    assert response.status_code == 404


async def test_authenticated_download_order_returns_404_when_not_found() -> None:
    # Arrange
    from app.infrastructure.dependencies import get_order_service
    from app.infrastructure.errors.app_error import AppError

    mock_svc = AsyncMock()
    mock_svc.download_order.side_effect = AppError("Order not found", status_code=404)
    app.dependency_overrides[get_current_user] = lambda: _VALID_USER
    app.dependency_overrides[get_order_service] = lambda: mock_svc

    # Act
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/orders/some-order/download",
            headers={"Authorization": "Bearer fake"},
        )

    # Assert — endpoint is now implemented, 404 for missing order
    assert response.status_code == 404
