from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from app.domain.models.user import User

_NOW = datetime(2025, 1, 1, tzinfo=UTC)


def _valid_user(**overrides: object) -> User:
    defaults: dict[str, object] = {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "auth0_sub": "auth0|64abc123",
        "email": "user@example.com",
        "full_name": "John Doe",
        "created_at": _NOW,
    }
    defaults.update(overrides)
    return User(**defaults)  # type: ignore[arg-type]


def test_user_creation_with_valid_fields() -> None:
    # Arrange / Act
    user = _valid_user()

    # Assert
    assert user.id == "550e8400-e29b-41d4-a716-446655440000"
    assert user.auth0_sub == "auth0|64abc123"
    assert user.email == "user@example.com"
    assert user.full_name == "John Doe"
    assert user.created_at == _NOW


def test_user_full_name_can_be_none() -> None:
    user = _valid_user(full_name=None)
    assert user.full_name is None


def test_user_requires_auth0_sub() -> None:
    with pytest.raises(ValueError, match="auth0_sub is required"):
        _valid_user(auth0_sub="")


def test_user_requires_email() -> None:
    with pytest.raises(ValueError, match="email is required and must be valid"):
        _valid_user(email="")


def test_user_requires_valid_email_format() -> None:
    with pytest.raises(ValueError, match="email is required and must be valid"):
        _valid_user(email="not-an-email")


def test_user_is_immutable() -> None:
    user = _valid_user()
    with pytest.raises(FrozenInstanceError):
        user.email = "other@example.com"  # type: ignore[misc]
