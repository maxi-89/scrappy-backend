from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.user import User
from app.domain.repositories.i_user_repository import IUserRepository
from app.infrastructure.database.orm_models import UserORM


class UserRepository(IUserRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_auth0_sub(self, auth0_sub: str) -> User | None:
        result = await self._session.execute(select(UserORM).where(UserORM.auth0_sub == auth0_sub))
        orm = result.scalar_one_or_none()
        return self._map_to_domain(orm) if orm else None

    async def create(self, user: User) -> User:
        orm = UserORM(
            id=user.id,
            auth0_sub=user.auth0_sub,
            email=user.email,
            full_name=user.full_name,
            created_at=user.created_at,
        )
        self._session.add(orm)
        await self._session.commit()
        await self._session.refresh(orm)
        return self._map_to_domain(orm)

    def _map_to_domain(self, orm: UserORM) -> User:
        return User(
            id=orm.id,
            auth0_sub=orm.auth0_sub,
            email=orm.email,
            full_name=orm.full_name,
            created_at=orm.created_at,
        )
