# Backend Implementation Plan: SCRUM-7 — Sync Auth0 user to local users table on first login

## 1. Overview

En cada request autenticado, el backend debe garantizar que el usuario de Auth0 tenga un registro en la tabla local `users`. Si el usuario no existe se crea; si ya existe se omite (idempotente). La sincronización ocurre dentro del dependency `get_current_user`, que se convierte en async, sin exponer ningún endpoint nuevo.

**Capas involucradas**: Domain · Application · Infrastructure · Presentation (solo modificación de dependency)

**Principios DDD aplicados**:
- Entidad `User` sin dependencias externas (dominio puro)
- Interfaz `IUserRepository` define el contrato; la implementación SQLAlchemy vive en infrastructure
- `UserService` orquesta sin importar FastAPI ni SQLAlchemy directamente
- Dependency injection via `Depends()` en FastAPI

---

## 2. Architecture Context

### Archivos a crear

| Archivo | Capa | Descripción |
|---|---|---|
| `app/domain/models/user.py` | Domain | Entidad `User` como `@dataclass` |
| `app/domain/repositories/i_user_repository.py` | Domain | Interfaz abstracta `IUserRepository` |
| `app/infrastructure/database/orm_models.py` | Infrastructure | ORM `UserORM` con SQLAlchemy |
| `app/infrastructure/repositories/__init__.py` | Infrastructure | Módulo vacío |
| `app/infrastructure/repositories/user_repository.py` | Infrastructure | Implementación `UserRepository` |
| `app/application/services/user_service.py` | Application | `UserService.sync_user()` |
| `tests/unit/domain/test_user.py` | Tests | Tests del modelo `User` |
| `tests/unit/application/test_user_service.py` | Tests | Tests del servicio |

### Archivos a modificar

| Archivo | Cambio |
|---|---|
| `app/infrastructure/database/orm_models.py` | Crear desde cero (no existe aún) |
| `app/infrastructure/dependencies.py` | Hacer `get_current_user` async + inyectar `UserService` |
| `app/infrastructure/database/session.py` | Agregar `Base` declarativa para ORM |
| `openspec/specs/data-model.md` | Agregar columna `auth0_sub` a tabla `users` |
| `tests/unit/presentation/test_orders_router_auth.py` | Actualizar tests de JWT inválido para evitar acceso real a DB |

### Dependencias entre componentes

```
get_current_user
    └─► verify_token (existente — valida JWT)
    └─► UserService.sync_user
            └─► IUserRepository.find_by_auth0_sub
            └─► IUserRepository.create
                    └─► AsyncSession (SQLAlchemy)
```

---

## 3. Implementation Steps

### Step 0: Crear feature branch

```bash
git checkout master
git pull origin master
git checkout -b feature/SCRUM-7-backend
```

---

### Step 1: Entidad de dominio `User`

**Archivo**: `app/domain/models/user.py`

```python
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class User:
    id: str              # UUID generado por la app (string)
    auth0_sub: str       # Auth0 subject, ej: "auth0|64abc..."
    email: str
    full_name: str | None
    created_at: datetime

    def __post_init__(self) -> None:
        if not self.auth0_sub:
            raise ValueError("auth0_sub is required")
        if not self.email or "@" not in self.email:
            raise ValueError("email is required and must be valid")
```

**Notas**:
- `frozen=True` porque es inmutable una vez creada
- `id` es `str` (UUID formateado como string), no `uuid.UUID`, para simplicidad de mapeo
- `__post_init__` valida invariantes del dominio
- Cero dependencias de FastAPI, SQLAlchemy o Supabase

---

### Step 2: Interfaz del repositorio

**Archivo**: `app/domain/repositories/i_user_repository.py`

```python
from abc import ABC, abstractmethod
from app.domain.models.user import User


class IUserRepository(ABC):

    @abstractmethod
    async def find_by_auth0_sub(self, auth0_sub: str) -> User | None:
        ...

    @abstractmethod
    async def create(self, user: User) -> User:
        ...
```

**Notas**:
- Métodos async porque la implementación usa SQLAlchemy async
- El dominio define la interfaz, la infra la implementa

---

### Step 3: Base declarativa y ORM model

**Archivo**: `app/infrastructure/database/orm_models.py` (nuevo)

Define `Base` (DeclarativeBase) y `UserORM`.

```python
from datetime import datetime
from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class UserORM(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    auth0_sub: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    full_name: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
```

**Modificación en `session.py`**: importar `Base` desde `orm_models` para que Alembic pueda detectarla.

En `app/infrastructure/database/session.py`, agregar al final:

```python
from app.infrastructure.database.orm_models import Base  # noqa: F401 — needed by Alembic
```

---

### Step 4: Configurar Alembic y generar migración

Alembic aún no está inicializado en el proyecto.

```bash
# Inicializar Alembic
uv run alembic init alembic
```

**Modificar `alembic/env.py`**:
- Importar `Base` desde `app.infrastructure.database.orm_models`
- Asignar `target_metadata = Base.metadata`
- Configurar `DATABASE_URL` desde `os.environ`
- Usar modo async (`run_async_migrations`)

**Modificar `alembic.ini`**:
- Vaciar `sqlalchemy.url` (se setea dinámicamente en `env.py`)

**Generar migración**:
```bash
uv run alembic revision --autogenerate -m "add users table with auth0_sub"
```

Verificar manualmente que la migración generada incluya:
- `CREATE TABLE users` con columnas `id`, `auth0_sub`, `email`, `full_name`, `created_at`
- `CREATE UNIQUE INDEX` en `auth0_sub`
- `CREATE UNIQUE INDEX` en `email`

---

### Step 5: Implementación SQLAlchemy del repositorio

**Archivo**: `app/infrastructure/repositories/user_repository.py`

```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.user import User
from app.domain.repositories.i_user_repository import IUserRepository
from app.infrastructure.database.orm_models import UserORM


class UserRepository(IUserRepository):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_auth0_sub(self, auth0_sub: str) -> User | None:
        result = await self._session.execute(
            select(UserORM).where(UserORM.auth0_sub == auth0_sub)
        )
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
```

---

### Step 6: Servicio de aplicación

**Archivo**: `app/application/services/user_service.py`

```python
import uuid
from datetime import datetime, timezone

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
            created_at=datetime.now(tz=timezone.utc),
        )
        return await self._repository.create(new_user)
```

**Notas**:
- Sin imports de FastAPI, SQLAlchemy, ni DB clients
- Construye la entidad `User` con UUID generado en la app
- `find_by_auth0_sub` antes de `create` garantiza idempotencia

---

### Step 7: Dependency injection

**Archivo**: `app/infrastructure/dependencies.py`

Agregar las nuevas funciones de wiring y modificar `get_current_user`:

```python
from collections.abc import AsyncGenerator
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
```

**Notas sobre tests existentes**:
- Tests que usan `app.dependency_overrides[get_current_user] = lambda: _VALID_USER` no se ven afectados: el override reemplaza toda la función, incluyendo la inyección de `UserService`.
- Tests que parchean el JWT verifier (invalido/expirado) necesitan evitar que `get_user_service` intente conectar a una DB real. Solución: agregar `app.dependency_overrides[get_user_service] = lambda: MagicMock()` en esos tests, o bien agregar un override de `get_db_session` en el fixture `conftest.py` global.
- La forma más limpia: en `conftest.py` (o en el fixture `autouse` del test file), también hacer `app.dependency_overrides[get_user_service] = lambda: MagicMock()` solo para los tests de JWT inválido.

---

### Step 8: Unit tests

#### `tests/unit/domain/test_user.py` (nuevo)

Casos:
- `test_user_creation_with_valid_fields` — instancia correcta
- `test_user_requires_auth0_sub` — `ValueError` si `auth0_sub` vacío
- `test_user_requires_email` — `ValueError` si `email` vacío
- `test_user_requires_valid_email_format` — `ValueError` si sin `@`
- `test_user_is_immutable` — `FrozenInstanceError` al intentar modificar

#### `tests/unit/application/test_user_service.py` (nuevo)

Usar un repositorio en memoria (fake), **no mocks de SQLAlchemy**.

```python
class InMemoryUserRepository(IUserRepository):
    def __init__(self) -> None:
        self._store: dict[str, User] = {}

    async def find_by_auth0_sub(self, auth0_sub: str) -> User | None:
        return next((u for u in self._store.values() if u.auth0_sub == auth0_sub), None)

    async def create(self, user: User) -> User:
        self._store[user.id] = user
        return user
```

Casos:
- `test_sync_user_creates_user_if_not_exists` — primer llamado crea registro
- `test_sync_user_does_not_duplicate_if_already_exists` — segundo llamado retorna el mismo usuario, sin duplicar
- `test_sync_user_uses_sub_as_auth0_sub` — valida que `user.auth0_sub == current_user.sub`
- `test_sync_user_uses_email_from_current_user` — valida que `user.email == current_user.email`

#### `tests/unit/presentation/test_orders_router_auth.py` (modificar)

En los tests que parchean JWT (invalid/expired), agregar override de `get_user_service`:

```python
from unittest.mock import AsyncMock, MagicMock
from app.infrastructure.dependencies import get_user_service

# En cada test de JWT inválido:
app.dependency_overrides[get_user_service] = lambda: MagicMock(
    sync_user=AsyncMock(return_value=None)
)
```

O bien centralizar en el fixture `autouse=True` existente del archivo.

---

### Step 9: Actualizar documentación

**`openspec/specs/data-model.md`**: agregar columna `auth0_sub` a la tabla `users`:

```markdown
| `auth0_sub` | `text` | NOT NULL, UNIQUE | Auth0 subject identifier (e.g. `auth0|64abc...`) |
```

Y actualizar la nota:
```markdown
> Auth is managed by **Auth0**. The `users` table stores application-level data.
> `auth0_sub` maps the Auth0 identity to the local record.
```

---

## 4. Implementation Order

1. **Step 0** — Feature branch
2. **Step 1** — Entidad `User` (`app/domain/models/user.py`)
3. **Step 2** — Interfaz `IUserRepository` (`app/domain/repositories/i_user_repository.py`)
4. **Step 3** — ORM `UserORM` (`app/infrastructure/database/orm_models.py`) + ajuste en `session.py`
5. **Step 4** — Alembic init + migración
6. **Step 5** — Repositorio SQLAlchemy (`app/infrastructure/repositories/user_repository.py`)
7. **Step 6** — Servicio (`app/application/services/user_service.py`)
8. **Step 7** — Dependency injection (`app/infrastructure/dependencies.py`)
9. **Step 8** — Unit tests (dominio → servicio → presentación)
10. **Step 9** — Documentación

---

## 5. Error Response Format

No se agrega ningún endpoint nuevo. Los errores son los mismos del dependency actual:

| Situación | HTTP | Body |
|---|---|---|
| Sin token | 401 | `{"error": "Missing authentication token"}` |
| Token inválido | 401 | `{"error": "Invalid authentication token"}` |
| Token expirado | 401 | `{"error": "Authentication token expired"}` |
| Error de DB al crear usuario | 500 | `{"error": "<mensaje interno>"}` (via `AppError`) |

---

## 6. Testing Checklist

- [ ] `test_user_requires_auth0_sub` — dominio rechaza sub vacío
- [ ] `test_user_requires_email` — dominio rechaza email vacío o sin `@`
- [ ] `test_user_is_immutable` — dataclass frozen
- [ ] `test_sync_user_creates_user_if_not_exists` — happy path creación
- [ ] `test_sync_user_does_not_duplicate_if_already_exists` — idempotencia
- [ ] `test_sync_user_uses_sub_as_auth0_sub` — mapeo correcto de campos
- [ ] Tests de JWT inválido siguen retornando 401 (sin regresiones)
- [ ] Tests de dependency override siguen funcionando
- [ ] Cobertura >= 90%
- [ ] Todos los tests siguen patrón AAA (Arrange / Act / Assert)

---

## 7. Dependencies

No se requieren nuevos paquetes. Alembic se agrega como dev dependency:

```toml
# En pyproject.toml, bajo [tool.uv] dev-dependencies
"alembic>=1.13.0",
```

> Alembic es necesario para gestionar migraciones de DB. Sin él no hay forma de aplicar el cambio de esquema de forma reproducible.

---

## 8. Notes

### Consideraciones arquitectónicas

- `get_current_user` pasa de `sync` a `async` — FastAPI soporta ambos de forma transparente. Los tests con `dependency_overrides` no se ven afectados.
- `UserService.sync_user` retorna `User` pero el router no lo usa directamente (sólo `CurrentUser` es retornado por `get_current_user`). Esto es correcto: la sincronización es un side effect, no parte de la respuesta.
- El `id` de `User` se genera en la app (no en la DB) para mantener el control en la capa de dominio.

### Variables de entorno requeridas

- `DATABASE_URL` — ya existente. Para tests: `sqlite+aiosqlite:///:memory:` (ya configurado en `conftest.py`).

### Alembic con SQLAlchemy async

`env.py` de Alembic debe usar `run_async_migrations()`. Consultar la documentación de Alembic para async engines.

### Decisión de diseño: `auth0_sub` vs usar `email` como lookup

Se eligió `auth0_sub` porque:
- Es el identificador primario e inmutable de Auth0 (el email puede cambiar)
- Permite futuros cambios de email sin perder la asociación con el usuario

---

## 9. Implementation Verification

- [ ] Entidad `User` sin imports de FastAPI, SQLAlchemy, ni clientes externos
- [ ] `UserService` sin imports de FastAPI ni SQLAlchemy
- [ ] `get_current_user` no contiene lógica de negocio — solo orquestación de dependencies
- [ ] `mypy --strict` pasa sin errores en todos los archivos nuevos
- [ ] `uv run pytest` — todos los tests pasan
- [ ] `uv run pytest --cov=app --cov-report=term-missing` — cobertura >= 90%
- [ ] `uv run ruff check . --fix && uv run ruff format .` — sin errores de linting
- [ ] Documentación actualizada (`data-model.md`)
