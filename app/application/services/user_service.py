import uuid
from datetime import UTC, datetime

from app.domain.models.current_user import CurrentUser
from app.domain.models.user import User
from app.domain.repositories.i_user_repository import IUserRepository


class UserService:
    def __init__(self, repository: IUserRepository) -> None:
        self._repository = repository

    async def sync_user(self, current_user: CurrentUser) -> User:
        existing = await self._repository.find_by_auth0_sub(current_user.sub)
        if existing:
            return existing
        new_user = User(
            id=str(uuid.uuid4()),
            auth0_sub=current_user.sub,
            email=current_user.email,
            full_name=None,
            created_at=datetime.now(tz=UTC),
        )
        return await self._repository.create(new_user)
