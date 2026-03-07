from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.domain.models.current_user import CurrentUser
from app.infrastructure.auth.auth0_jwt_verifier import verify_token
from app.infrastructure.errors.app_error import AppError

_bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> CurrentUser:
    if credentials is None:
        raise AppError("Missing authentication token", status_code=401)
    return verify_token(credentials.credentials)
