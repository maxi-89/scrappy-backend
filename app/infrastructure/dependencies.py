from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.user_service import UserService
from app.domain.models.current_user import CurrentUser
from app.domain.repositories.i_user_repository import IUserRepository
from app.infrastructure.auth.auth0_jwt_verifier import verify_token
from app.infrastructure.database.session import get_db_session
from app.infrastructure.errors.app_error import AppError
from app.infrastructure.repositories.user_repository import UserRepository

_bearer_scheme = HTTPBearer(auto_error=False)


def get_user_repository(
    session: AsyncSession = Depends(get_db_session),
) -> IUserRepository:
    return UserRepository(session)


def get_user_service(
    repository: IUserRepository = Depends(get_user_repository),
) -> UserService:
    return UserService(repository)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    user_service: UserService = Depends(get_user_service),
) -> CurrentUser:
    if credentials is None:
        raise AppError("Missing authentication token", status_code=401)
    current_user = verify_token(credentials.credentials)
    await user_service.sync_user(current_user)
    return current_user
