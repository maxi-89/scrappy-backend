from abc import ABC, abstractmethod

from app.domain.models.user import User


class IUserRepository(ABC):
    @abstractmethod
    async def find_by_auth0_sub(self, auth0_sub: str) -> User | None: ...

    @abstractmethod
    async def create(self, user: User) -> User: ...
