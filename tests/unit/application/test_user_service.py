from app.application.services.user_service import UserService
from app.domain.models.current_user import CurrentUser
from app.domain.models.user import User
from app.domain.repositories.i_user_repository import IUserRepository

_CURRENT_USER = CurrentUser(sub="auth0|64abc123", email="user@example.com")


class InMemoryUserRepository(IUserRepository):
    def __init__(self) -> None:
        self._store: dict[str, User] = {}

    async def find_by_auth0_sub(self, auth0_sub: str) -> User | None:
        return next((u for u in self._store.values() if u.auth0_sub == auth0_sub), None)

    async def create(self, user: User) -> User:
        self._store[user.id] = user
        return user


def _make_service() -> tuple[UserService, InMemoryUserRepository]:
    repo = InMemoryUserRepository()
    service = UserService(repository=repo)
    return service, repo


async def test_sync_user_creates_user_if_not_exists() -> None:
    # Arrange
    service, repo = _make_service()

    # Act
    user = await service.sync_user(_CURRENT_USER)

    # Assert
    assert user.auth0_sub == _CURRENT_USER.sub
    assert user.email == _CURRENT_USER.email
    assert len(repo._store) == 1


async def test_sync_user_does_not_duplicate_if_already_exists() -> None:
    # Arrange
    service, repo = _make_service()
    first = await service.sync_user(_CURRENT_USER)

    # Act
    second = await service.sync_user(_CURRENT_USER)

    # Assert
    assert first.id == second.id
    assert len(repo._store) == 1


async def test_sync_user_uses_sub_as_auth0_sub() -> None:
    # Arrange
    service, _ = _make_service()

    # Act
    user = await service.sync_user(_CURRENT_USER)

    # Assert
    assert user.auth0_sub == _CURRENT_USER.sub


async def test_sync_user_uses_email_from_current_user() -> None:
    # Arrange
    service, _ = _make_service()

    # Act
    user = await service.sync_user(_CURRENT_USER)

    # Assert
    assert user.email == _CURRENT_USER.email


async def test_sync_user_sets_full_name_to_none() -> None:
    # Arrange
    service, _ = _make_service()

    # Act
    user = await service.sync_user(_CURRENT_USER)

    # Assert
    assert user.full_name is None


async def test_sync_user_generates_unique_id_per_user() -> None:
    # Arrange
    service, _ = _make_service()
    user_a = CurrentUser(sub="auth0|aaa", email="a@example.com")
    user_b = CurrentUser(sub="auth0|bbb", email="b@example.com")

    # Act
    result_a = await service.sync_user(user_a)
    result_b = await service.sync_user(user_b)

    # Assert
    assert result_a.id != result_b.id
