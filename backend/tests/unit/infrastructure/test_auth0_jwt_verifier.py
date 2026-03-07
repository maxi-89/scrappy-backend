from unittest.mock import MagicMock, patch

import pytest

from app.domain.models.current_user import CurrentUser
from app.infrastructure.errors.app_error import AppError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_PAYLOAD = {"sub": "auth0|123", "email": "user@test.com"}
_FAKE_TOKEN = "header.payload.signature"
_AUTH0_DOMAIN = "scrappy.us.auth0.com"
_AUTH0_AUDIENCE = "https://api.scrappy.io"


def _make_mock_signing_key() -> MagicMock:
    signing_key = MagicMock()
    signing_key.key = "fake-rsa-key"
    return signing_key


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@patch.dict(
    "os.environ",
    {"AUTH0_DOMAIN": _AUTH0_DOMAIN, "AUTH0_AUDIENCE": _AUTH0_AUDIENCE},
)
@patch("app.infrastructure.auth.auth0_jwt_verifier._get_jwks_client")
@patch("app.infrastructure.auth.auth0_jwt_verifier.jwt.decode")
def test_verify_token_returns_current_user_on_valid_payload(
    mock_decode: MagicMock, mock_get_client: MagicMock
) -> None:
    # Arrange
    mock_get_client.return_value.get_signing_key_from_jwt.return_value = _make_mock_signing_key()
    mock_decode.return_value = _VALID_PAYLOAD

    from app.infrastructure.auth.auth0_jwt_verifier import verify_token

    # Act
    result = verify_token(_FAKE_TOKEN)

    # Assert
    assert isinstance(result, CurrentUser)
    assert result.sub == "auth0|123"
    assert result.email == "user@test.com"


@patch.dict(
    "os.environ",
    {"AUTH0_DOMAIN": _AUTH0_DOMAIN, "AUTH0_AUDIENCE": _AUTH0_AUDIENCE},
)
@patch("app.infrastructure.auth.auth0_jwt_verifier._get_jwks_client")
@patch("app.infrastructure.auth.auth0_jwt_verifier.jwt.decode")
def test_verify_token_raises_app_error_401_on_expired_token(
    mock_decode: MagicMock, mock_get_client: MagicMock
) -> None:
    # Arrange
    from jwt import ExpiredSignatureError

    mock_get_client.return_value.get_signing_key_from_jwt.return_value = _make_mock_signing_key()
    mock_decode.side_effect = ExpiredSignatureError("expired")

    from app.infrastructure.auth.auth0_jwt_verifier import verify_token

    # Act / Assert
    with pytest.raises(AppError) as exc_info:
        verify_token(_FAKE_TOKEN)

    assert exc_info.value.status_code == 401
    assert str(exc_info.value) == "Authentication token expired"


@patch.dict(
    "os.environ",
    {"AUTH0_DOMAIN": _AUTH0_DOMAIN, "AUTH0_AUDIENCE": _AUTH0_AUDIENCE},
)
@patch("app.infrastructure.auth.auth0_jwt_verifier._get_jwks_client")
@patch("app.infrastructure.auth.auth0_jwt_verifier.jwt.decode")
def test_verify_token_raises_app_error_401_on_invalid_token(
    mock_decode: MagicMock, mock_get_client: MagicMock
) -> None:
    # Arrange
    from jwt import InvalidTokenError

    mock_get_client.return_value.get_signing_key_from_jwt.return_value = _make_mock_signing_key()
    mock_decode.side_effect = InvalidTokenError("invalid")

    from app.infrastructure.auth.auth0_jwt_verifier import verify_token

    # Act / Assert
    with pytest.raises(AppError) as exc_info:
        verify_token(_FAKE_TOKEN)

    assert exc_info.value.status_code == 401
    assert str(exc_info.value) == "Invalid authentication token"


@patch.dict(
    "os.environ",
    {"AUTH0_DOMAIN": _AUTH0_DOMAIN, "AUTH0_AUDIENCE": _AUTH0_AUDIENCE},
)
@patch("app.infrastructure.auth.auth0_jwt_verifier._get_jwks_client")
@patch("app.infrastructure.auth.auth0_jwt_verifier.jwt.decode")
def test_verify_token_uses_rs256_algorithm(
    mock_decode: MagicMock, mock_get_client: MagicMock
) -> None:
    # Arrange
    mock_get_client.return_value.get_signing_key_from_jwt.return_value = _make_mock_signing_key()
    mock_decode.return_value = _VALID_PAYLOAD

    from app.infrastructure.auth.auth0_jwt_verifier import verify_token

    # Act
    verify_token(_FAKE_TOKEN)

    # Assert
    _, kwargs = mock_decode.call_args
    assert kwargs["algorithms"] == ["RS256"]


@patch.dict(
    "os.environ",
    {"AUTH0_DOMAIN": _AUTH0_DOMAIN, "AUTH0_AUDIENCE": _AUTH0_AUDIENCE},
)
@patch("app.infrastructure.auth.auth0_jwt_verifier._get_jwks_client")
@patch("app.infrastructure.auth.auth0_jwt_verifier.jwt.decode")
def test_verify_token_validates_audience(
    mock_decode: MagicMock, mock_get_client: MagicMock
) -> None:
    # Arrange
    mock_get_client.return_value.get_signing_key_from_jwt.return_value = _make_mock_signing_key()
    mock_decode.return_value = _VALID_PAYLOAD

    from app.infrastructure.auth.auth0_jwt_verifier import verify_token

    # Act
    verify_token(_FAKE_TOKEN)

    # Assert
    _, kwargs = mock_decode.call_args
    assert kwargs["audience"] == _AUTH0_AUDIENCE


@patch.dict(
    "os.environ",
    {"AUTH0_DOMAIN": _AUTH0_DOMAIN, "AUTH0_AUDIENCE": _AUTH0_AUDIENCE},
)
@patch("app.infrastructure.auth.auth0_jwt_verifier._get_jwks_client")
@patch("app.infrastructure.auth.auth0_jwt_verifier.jwt.decode")
def test_verify_token_validates_issuer(mock_decode: MagicMock, mock_get_client: MagicMock) -> None:
    # Arrange
    mock_get_client.return_value.get_signing_key_from_jwt.return_value = _make_mock_signing_key()
    mock_decode.return_value = _VALID_PAYLOAD

    from app.infrastructure.auth.auth0_jwt_verifier import verify_token

    # Act
    verify_token(_FAKE_TOKEN)

    # Assert
    _, kwargs = mock_decode.call_args
    assert kwargs["issuer"] == f"https://{_AUTH0_DOMAIN}/"
