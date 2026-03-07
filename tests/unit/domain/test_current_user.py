from dataclasses import FrozenInstanceError

import pytest

from app.domain.models.current_user import CurrentUser


def test_current_user_stores_sub_and_email() -> None:
    # Arrange / Act
    user = CurrentUser(sub="auth0|64abc123", email="user@example.com")

    # Assert
    assert user.sub == "auth0|64abc123"
    assert user.email == "user@example.com"


def test_current_user_is_frozen() -> None:
    # Arrange
    user = CurrentUser(sub="auth0|64abc123", email="user@example.com")

    # Act / Assert
    with pytest.raises(FrozenInstanceError):
        user.sub = "other"  # type: ignore[misc]


def test_current_user_equality() -> None:
    # Arrange
    user_a = CurrentUser(sub="auth0|64abc123", email="user@example.com")
    user_b = CurrentUser(sub="auth0|64abc123", email="user@example.com")

    # Assert
    assert user_a == user_b
