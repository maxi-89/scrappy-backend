"""Tests for webhooks router (SCRUM-19)."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.infrastructure.dependencies import get_webhook_service
from app.infrastructure.errors.app_error import AppError
from main import app


@pytest.fixture(autouse=True)
def clear_overrides() -> None:  # type: ignore[misc]
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def mock_service() -> AsyncMock:
    svc = AsyncMock()
    svc.handle_event.return_value = None
    return svc


async def test_stripe_webhook_returns_200(mock_service: AsyncMock) -> None:
    app.dependency_overrides[get_webhook_service] = lambda: mock_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/webhooks/stripe",
            content=b'{"type": "payment_intent.succeeded"}',
            headers={"Stripe-Signature": "t=123,v1=abc"},
        )

    assert response.status_code == 200
    mock_service.handle_event.assert_called_once()


async def test_stripe_webhook_passes_raw_body_and_sig(mock_service: AsyncMock) -> None:
    app.dependency_overrides[get_webhook_service] = lambda: mock_service
    raw = b'{"type": "payment_intent.succeeded"}'

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/webhooks/stripe",
            content=raw,
            headers={"stripe-signature": "t=123,v1=abc"},
        )

    call_args = mock_service.handle_event.call_args[0]
    assert call_args[0] == raw
    assert call_args[1] == "t=123,v1=abc"


async def test_stripe_webhook_invalid_signature_returns_400(mock_service: AsyncMock) -> None:
    app.dependency_overrides[get_webhook_service] = lambda: mock_service
    mock_service.handle_event.side_effect = AppError("Invalid Stripe signature", status_code=400)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/webhooks/stripe",
            content=b"{}",
            headers={"stripe-signature": "bad"},
        )

    assert response.status_code == 400


async def test_stripe_webhook_missing_signature_returns_400(mock_service: AsyncMock) -> None:
    app.dependency_overrides[get_webhook_service] = lambda: mock_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/webhooks/stripe", content=b"{}")

    assert response.status_code == 400
