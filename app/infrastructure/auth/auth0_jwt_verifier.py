import os
from functools import lru_cache

import jwt
from jwt import ExpiredSignatureError, InvalidTokenError, PyJWKClient

from app.domain.models.current_user import CurrentUser
from app.infrastructure.errors.app_error import AppError


@lru_cache(maxsize=1)
def _get_jwks_client() -> PyJWKClient:  # pragma: no cover
    domain = os.environ["AUTH0_DOMAIN"]
    jwks_url = f"https://{domain}/.well-known/jwks.json"
    return PyJWKClient(jwks_url)


def verify_token(token: str) -> CurrentUser:
    domain = os.environ["AUTH0_DOMAIN"]
    audience = os.environ["AUTH0_AUDIENCE"]
    client = _get_jwks_client()
    try:
        signing_key = client.get_signing_key_from_jwt(token)
        payload: dict[str, object] = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=audience,
            issuer=f"https://{domain}/",
        )
        return CurrentUser(
            sub=str(payload["sub"]),
            email=str(payload.get("email", "")),
        )
    except ExpiredSignatureError:
        raise AppError("Authentication token expired", status_code=401)
    except InvalidTokenError:
        raise AppError("Invalid authentication token", status_code=401)
