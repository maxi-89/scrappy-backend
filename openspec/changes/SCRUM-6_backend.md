# Backend Implementation Plan: SCRUM-6 — Auth0 JWT Validation Middleware

## 1. Overview

Implement a reusable FastAPI dependency (`get_current_user`) that validates Auth0 Bearer JWT tokens
on every protected endpoint. The dependency extracts the Bearer token from the `Authorization`
header, validates it against Auth0's JWKS endpoint using RS256, and returns a typed `CurrentUser`
domain object to the route handler.

Since this is the **first backend story**, the plan also covers bootstrapping the project skeleton
(folder structure, `pyproject.toml`, `main.py`, error classes) as a prerequisite.

**Layers involved:**
- **Domain** — `CurrentUser` frozen dataclass
- **Infrastructure** — JWT verifier, error classes, DB session, dependency injection
- **Presentation** — orders router stub with auth applied, global error handler in `main.py`

**DDD principles applied:**
- `CurrentUser` lives in the domain layer with zero external dependencies
- JWT verification logic lives in the infrastructure layer (external service adapter)
- The FastAPI `Depends` factory lives in `dependencies.py` (infrastructure wiring)
- Routers receive a fully typed `CurrentUser` — no token logic in route handlers

---

## 2. Architecture Context

### Files to create

```
backend/
├── pyproject.toml                                         ← project deps + tooling config
├── main.py                                                ← FastAPI app + Mangum handler + exception handlers
├── .env.example                                           ← env var documentation
├── app/
│   ├── __init__.py
│   ├── domain/
│   │   ├── __init__.py
│   │   └── models/
│   │       ├── __init__.py
│   │       └── current_user.py                           ← CurrentUser frozen dataclass
│   ├── application/
│   │   ├── __init__.py
│   │   └── services/
│   │       └── __init__.py
│   ├── infrastructure/
│   │   ├── __init__.py
│   │   ├── auth/
│   │   │   ├── __init__.py
│   │   │   └── auth0_jwt_verifier.py                     ← verify_token() with JWKS + lru_cache
│   │   ├── database/
│   │   │   ├── __init__.py
│   │   │   └── session.py                                ← SQLAlchemy async session (stub)
│   │   ├── errors/
│   │   │   ├── __init__.py
│   │   │   ├── app_error.py                              ← AppError(Exception)
│   │   │   └── domain_validation_error.py                ← DomainValidationError(Exception)
│   │   └── dependencies.py                               ← get_current_user + get_db_session
│   └── presentation/
│       ├── __init__.py
│       └── routers/
│           ├── __init__.py
│           └── orders_router.py                          ← stub router with auth applied
└── tests/
    ├── __init__.py
    ├── unit/
    │   ├── __init__.py
    │   ├── domain/
    │   │   ├── __init__.py
    │   │   └── test_current_user.py
    │   ├── infrastructure/
    │   │   ├── __init__.py
    │   │   └── test_auth0_jwt_verifier.py
    │   └── presentation/
    │       ├── __init__.py
    │       └── test_orders_router_auth.py
    └── conftest.py
```

### Dependency graph

```
main.py
  └─ orders_router.py
       └─ get_current_user (dependencies.py)
            └─ verify_token (auth0_jwt_verifier.py)
                 └─ CurrentUser (domain/models/current_user.py)
                 └─ AppError   (infrastructure/errors/app_error.py)

main.py
  └─ exception_handler(AppError)     → { "error": "..." } JSON
  └─ exception_handler(DomainValidationError) → { "error": "..." } JSON
```

---

## 3. Implementation Steps

> **TDD approach**: for each component, write the failing test first, then the implementation.

---

### Step 0: Create Feature Branch

- **Action**: Create and switch to the feature branch
- **Branch name**: `feature/SCRUM-6-backend`
- **Steps**:
  1. `git checkout main && git pull origin main`
  2. `git checkout -b feature/SCRUM-6-backend`
  3. Verify with `git branch`
- **Note**: All code changes happen after this step

---

### Step 1: Bootstrap Project Skeleton

#### 1a. `pyproject.toml`

Initialize the Python project with `uv`. Create `pyproject.toml` with the following:

**Runtime dependencies:**
```toml
[project]
name = "scrappy-backend"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "mangum>=0.19.0",
    "sqlalchemy[asyncio]>=2.0.0",
    "asyncpg>=0.29.0",
    "pydantic>=2.0.0",
    "PyJWT[cryptography]>=2.8.0",   # ← RS256 validation via JWKS
]
```

**Dev dependencies:**
```toml
[tool.uv]
dev-dependencies = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "httpx>=0.27.0",             # AsyncClient for router tests
    "pytest-cov>=5.0.0",
    "mypy>=1.10.0",
    "ruff>=0.4.0",
]
```

**Tooling config:**
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.mypy]
strict = true
python_version = "3.12"

[tool.ruff]
line-length = 100
target-version = "py312"
```

Install with: `uv sync`

#### 1b. Folder structure

Create all `__init__.py` files for every package listed in the file tree above. They should all be empty.

#### 1c. `.env.example`

```env
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/scrappy

# Auth0
AUTH0_DOMAIN=your-tenant.us.auth0.com
AUTH0_AUDIENCE=https://api.scrappy.io

# Environment
ENVIRONMENT=development
```

---

### Step 2: Error Classes

#### 2a. `app/infrastructure/errors/app_error.py`

```python
class AppError(Exception):
    def __init__(self, message: str, status_code: int = 500) -> None:
        super().__init__(message)
        self.status_code = status_code
```

#### 2b. `app/infrastructure/errors/domain_validation_error.py`

```python
class DomainValidationError(Exception):
    pass
```

---

### Step 3: `main.py` — FastAPI App + Exception Handlers

Create the FastAPI application entry point. Register the global exception handlers for `AppError`
and `DomainValidationError` so that all 401 responses (and others) follow the `{ "error": "..." }`
JSON shape automatically.

**Key requirements:**
- Import and `include_router` for `orders_router`
- Register `@app.exception_handler(AppError)` → `JSONResponse(status_code=exc.status_code, content={"error": str(exc)})`
- Register `@app.exception_handler(DomainValidationError)` → `JSONResponse(status_code=400, content={"error": str(exc)})`
- Add `handler = Mangum(app, lifespan="off")` for AWS Lambda

---

### Step 4: Database Session Stub

**File**: `app/infrastructure/database/session.py`

Create a minimal async session factory. This is a dependency stub needed so `dependencies.py`
compiles — it will be fully implemented in the database story.

```python
import os
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from collections.abc import AsyncGenerator

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
```

> **Note**: The SQLite fallback is for test isolation only. In production `DATABASE_URL` always
> points to Supabase via asyncpg. Add `aiosqlite` to dev dependencies if tests need it.

---

### Step 5 (TDD): Domain Model — `CurrentUser`

#### 5a. Write failing test first

**File**: `tests/unit/domain/test_current_user.py`

Test cases to cover:

| Test | Description |
|---|---|
| `test_current_user_stores_sub_and_email` | Instantiate with valid sub + email, assert both fields |
| `test_current_user_is_frozen` | Attempt `current_user.sub = "other"` → raises `FrozenInstanceError` |
| `test_current_user_equality` | Two instances with same sub+email are equal (`==`) |

**Run**: `uv run pytest tests/unit/domain/test_current_user.py` → must FAIL before implementation.

#### 5b. Implement `CurrentUser`

**File**: `app/domain/models/current_user.py`

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class CurrentUser:
    sub: str    # Auth0 user ID, e.g. "auth0|64abc123"
    email: str  # User email address
```

**Constraints:**
- Zero imports from FastAPI, SQLAlchemy, or any infrastructure package
- `frozen=True` makes it hashable and immutable (safe to use as dict key or in sets)

**Run**: `uv run pytest tests/unit/domain/test_current_user.py` → must PASS.

---

### Step 6 (TDD): JWT Verifier

#### 6a. Write failing tests first

**File**: `tests/unit/infrastructure/test_auth0_jwt_verifier.py`

Use `unittest.mock.patch` to mock `PyJWKClient.get_signing_key_from_jwt` and `jwt.decode`
so that no real Auth0 network calls are made.

Test cases:

| Test | Mock setup | Expected outcome |
|---|---|---|
| `test_verify_token_returns_current_user_on_valid_payload` | `jwt.decode` returns `{"sub": "auth0\|123", "email": "user@test.com"}` | Returns `CurrentUser(sub="auth0\|123", email="user@test.com")` |
| `test_verify_token_raises_app_error_401_on_expired_token` | `jwt.decode` raises `ExpiredSignatureError` | Raises `AppError` with `status_code=401` and message `"Authentication token expired"` |
| `test_verify_token_raises_app_error_401_on_invalid_token` | `jwt.decode` raises `InvalidTokenError` | Raises `AppError` with `status_code=401` and message `"Invalid authentication token"` |
| `test_verify_token_uses_rs256_algorithm` | Capture `jwt.decode` call args | `algorithms=["RS256"]` is passed |
| `test_verify_token_validates_audience` | Capture `jwt.decode` call args | `audience=AUTH0_AUDIENCE` is passed |
| `test_verify_token_validates_issuer` | Capture `jwt.decode` call args | `issuer=f"https://{AUTH0_DOMAIN}/"` is passed |

**Run**: `uv run pytest tests/unit/infrastructure/test_auth0_jwt_verifier.py` → must FAIL.

#### 6b. Implement `auth0_jwt_verifier.py`

**File**: `app/infrastructure/auth/auth0_jwt_verifier.py`

**Key implementation details:**

1. Read `AUTH0_DOMAIN` and `AUTH0_AUDIENCE` from `os.environ` at module level
2. Build `JWKS_URL = f"https://{AUTH0_DOMAIN}/.well-known/jwks.json"`
3. Cache the `PyJWKClient` instance with `@lru_cache(maxsize=1)` — one client per process
4. `verify_token(token: str) -> CurrentUser` function:
   - Call `_get_jwks_client().get_signing_key_from_jwt(token)` to fetch the matching RS256 key
   - Call `jwt.decode(token, signing_key.key, algorithms=["RS256"], audience=AUTH0_AUDIENCE, issuer=...)`
   - On `ExpiredSignatureError` → raise `AppError("Authentication token expired", status_code=401)`
   - On `InvalidTokenError` → raise `AppError("Invalid authentication token", status_code=401)`
   - On success → return `CurrentUser(sub=payload["sub"], email=payload.get("email", ""))`

**Note on `lru_cache`**: In AWS Lambda, the cache survives across warm invocations of the same
container. On cold starts it makes one JWKS fetch. This is the correct production behavior.

**Run**: `uv run pytest tests/unit/infrastructure/test_auth0_jwt_verifier.py` → must PASS.

---

### Step 7: FastAPI Dependency — `get_current_user`

**File**: `app/infrastructure/dependencies.py`

Add the `get_current_user` dependency function alongside the future `get_db_session` wiring:

**Key implementation details:**

1. Instantiate `_bearer_scheme = HTTPBearer(auto_error=False)` at module level
   - `auto_error=False` prevents FastAPI from returning its own 403 — we control the 401 ourselves
2. `get_current_user` receives `credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme)`
3. If `credentials is None` → raise `AppError("Missing authentication token", status_code=401)`
4. Otherwise → return `verify_token(credentials.credentials)`

The `AppError` raised here is caught by the global handler in `main.py` and serialized as
`{ "error": "Missing authentication token" }` with HTTP 401.

---

### Step 8 (TDD): Router Auth Tests

#### 8a. Write failing tests first

**File**: `tests/unit/presentation/test_orders_router_auth.py`

Use `httpx.AsyncClient` with `ASGITransport(app=app)` and `app.dependency_overrides` for mocking.

Test cases:

| Test | Setup | Request | Expected |
|---|---|---|---|
| `test_orders_returns_401_when_no_authorization_header` | No override | `GET /orders` (no header) | 401, `{"error": "Missing authentication token"}` |
| `test_orders_returns_401_when_token_is_invalid` | Mock `verify_token` raises `AppError(..., 401)` | `GET /orders` with `Authorization: Bearer bad.token` | 401, `{"error": "Invalid authentication token"}` |
| `test_create_order_returns_401_when_no_authorization_header` | No override | `POST /orders` (no header) | 401, `{"error": "Missing authentication token"}` |
| `test_authenticated_request_passes_current_user_to_handler` | Override `get_current_user` → `CurrentUser(sub="auth0\|123", email="u@test.com")` | `GET /orders` with any header | Not 401 (handler receives user) |

**Run**: `uv run pytest tests/unit/presentation/test_orders_router_auth.py` → must FAIL.

#### 8b. Create `orders_router.py` stub

**File**: `app/presentation/routers/orders_router.py`

Create a minimal stub that declares the four order endpoints and injects `get_current_user`.
The handlers return `{"status": "not implemented"}` for now — they will be fully implemented
in the orders story.

**Endpoints to stub with `Depends(get_current_user)`:**

| Method | Path | Handler name |
|---|---|---|
| `POST` | `/orders` | `create_order` |
| `GET` | `/orders` | `list_orders` |
| `GET` | `/orders/{order_id}` | `get_order` |
| `GET` | `/orders/{order_id}/items/{item_id}/download` | `download_dataset` |

All four handlers must have `current_user: CurrentUser = Depends(get_current_user)` in their
signature. Return `{"status": "not implemented"}` with `status_code=501` for now.

**Run**: `uv run pytest tests/unit/presentation/test_orders_router_auth.py` → must PASS.

---

### Step 9: Register Router in `main.py`

**File**: `main.py`

- `from app.presentation.routers import orders_router`
- `app.include_router(orders_router.router, prefix="/orders", tags=["orders"])`

Verify: `uv run uvicorn main:app --reload` starts without errors and `/docs` shows all four order
endpoints with the lock icon (security scheme applied).

---

### Step 10: Run Full Test Suite + Linting

```bash
# Tests with coverage
uv run pytest --cov=app --cov-report=term-missing

# Type checking
uv run mypy app/

# Linting
uv run ruff check .
```

All three must exit with 0 errors. Coverage must be ≥ 90% for branches, functions, statements.

---

### Step 11: Update Documentation

No new endpoints are added in this story (orders stubs are not the real implementation), so
`api-spec.yml` does not change.

**`openspec/specs/api-spec.yml`:**
- Verify `BearerAuth` securityScheme is already defined (it is — check section `components.securitySchemes`)
- Verify all order endpoints already declare `security: - BearerAuth: []` (they do)
- No changes needed unless discrepancies are found

**`openspec/specs/development_guide.md`:**
- Add section: **Backend Local Setup**
  - Prerequisites: Python 3.12+, `uv`
  - Install: `uv sync`
  - Run locally: `uv run uvicorn main:app --reload`
  - Run tests: `uv run pytest --cov=app`
  - Type check: `uv run mypy app/`
  - Lint: `uv run ruff check .`
  - Required env vars: copy `.env.example` to `.env` and fill `AUTH0_DOMAIN`, `AUTH0_AUDIENCE`

---

## 4. Implementation Order

0. Create branch `feature/SCRUM-6-backend`
1. Bootstrap: `pyproject.toml` + folder skeleton + `.env.example` → `uv sync`
2. Error classes: `app_error.py`, `domain_validation_error.py`
3. DB session stub: `app/infrastructure/database/session.py`
4. `main.py` — FastAPI app + exception handlers (no routers yet)
5. *(TDD)* Write `tests/unit/domain/test_current_user.py` → run → FAIL
6. Implement `app/domain/models/current_user.py` → run → PASS
7. *(TDD)* Write `tests/unit/infrastructure/test_auth0_jwt_verifier.py` → run → FAIL
8. Implement `app/infrastructure/auth/auth0_jwt_verifier.py` → run → PASS
9. Implement `app/infrastructure/dependencies.py` (`get_current_user`)
10. *(TDD)* Write `tests/unit/presentation/test_orders_router_auth.py` → run → FAIL
11. Implement `app/presentation/routers/orders_router.py` stub → run → PASS
12. Register router in `main.py`
13. `uv run pytest --cov=app` + `uv run mypy app/` + `uv run ruff check .` — all green
14. Update `openspec/specs/development_guide.md`

---

## 5. Error Response Format

All error responses follow this JSON shape:

```json
{ "error": "Human-readable message" }
```

HTTP status code mapping for this story:

| Condition | Status | Error message |
|---|---|---|
| No `Authorization` header | 401 | `"Missing authentication token"` |
| Token malformed / signature invalid | 401 | `"Invalid authentication token"` |
| Token expired | 401 | `"Authentication token expired"` |
| `DomainValidationError` (any) | 400 | exception message |
| Unhandled exception | 500 | `"Internal server error"` |

The global handler in `main.py` catches `AppError` and uses `exc.status_code` to produce the
correct HTTP status. The same handler covers 401, 403, 404, 500 etc. across all future stories.

---

## 6. Testing Checklist

- [ ] `CurrentUser` dataclass: construction, immutability, equality
- [ ] `verify_token` happy path: returns correct `CurrentUser` from mocked payload
- [ ] `verify_token` expired token: raises `AppError(status_code=401)`
- [ ] `verify_token` invalid token: raises `AppError(status_code=401)`
- [ ] `verify_token` RS256 algorithm enforced (captured in call args)
- [ ] `verify_token` audience validated (captured in call args)
- [ ] `verify_token` issuer validated (captured in call args)
- [ ] Router: no Authorization header → 401 + correct JSON body
- [ ] Router: invalid token → 401 + correct JSON body
- [ ] Router: valid token override → handler invoked (not 401)
- [ ] All tests follow AAA (Arrange / Act / Assert) pattern
- [ ] `uv run pytest --cov=app` reports ≥ 90% coverage
- [ ] No test uses `Any` — all mocks are typed

---

## 7. Dependencies

| Package | Version | Justification |
|---|---|---|
| `PyJWT[cryptography]` | `>=2.8.0` | RS256 JWT decoding + `PyJWKClient` for JWKS key fetching |
| `fastapi` | `>=0.115.0` | Web framework + `HTTPBearer` security scheme |
| `uvicorn[standard]` | `>=0.30.0` | ASGI server for local development |
| `mangum` | `>=0.19.0` | AWS Lambda adapter for FastAPI |
| `sqlalchemy[asyncio]` | `>=2.0.0` | Async ORM (session stub needed for `dependencies.py`) |
| `asyncpg` | `>=0.29.0` | Async PostgreSQL driver (Supabase) |
| `httpx` | dev `>=0.27.0` | `AsyncClient` for router tests with `ASGITransport` |
| `pytest-asyncio` | dev `>=0.23.0` | `asyncio_mode = "auto"` for async tests |

---

## 8. Notes

### Assumptions

- **Project is greenfield** — no Python files exist yet. Step 1 bootstraps the full skeleton.
- **JWT algorithm is RS256** — Auth0 default. Never accept HS256. The `algorithms=["RS256"]`
  argument in `jwt.decode` is mandatory and non-negotiable.
- **JWKS caching with `lru_cache`** — one network call per Lambda cold start. This is correct.
  Do not cache with a time-based expiry in this story; that is a future optimization.
- **Orders router is a stub** — the handlers return 501. Full orders implementation is a separate
  story. The stub exists here only to prove the auth dependency works end-to-end.
- **No user sync to `users` table** — out of scope for this story. When a token is valid, the
  `CurrentUser.sub` is available to downstream handlers, but no DB write happens here.
- **Admin endpoints are out of scope** — they use `X-Admin-Key` header, not JWT. Do not touch
  admin routes in this story.

### Environment Variables Required

| Variable | Example | Description |
|---|---|---|
| `AUTH0_DOMAIN` | `scrappy.us.auth0.com` | Auth0 tenant domain (no `https://`) |
| `AUTH0_AUDIENCE` | `https://api.scrappy.io` | API identifier registered in Auth0 dashboard |
| `DATABASE_URL` | `postgresql+asyncpg://...` | Supabase connection string (stub uses SQLite for tests) |

### Discrepancy to note

The `openspec/specs/api-spec.yml` describes `BearerAuth` as "Supabase Auth JWT token" but the
Jira ticket and project memory specify **Auth0** as the identity provider. The implementation
follows **Auth0** (JWKS at `https://{AUTH0_DOMAIN}/.well-known/jwks.json`). Update the
`api-spec.yml` description string from "Supabase Auth JWT token" to "Auth0 RS256 JWT token"
in the documentation step.

---

## 9. Implementation Verification

- [ ] Code follows DDD layered architecture — no cross-layer imports
- [ ] `CurrentUser` has zero imports from FastAPI, SQLAlchemy, or infrastructure
- [ ] `auth0_jwt_verifier.py` does not import FastAPI
- [ ] `orders_router.py` does not call `jwt.decode` directly — only uses `Depends(get_current_user)`
- [ ] `get_current_user` in `dependencies.py` does not import SQLAlchemy
- [ ] `main.py` global handler returns `{ "error": "..." }` for `AppError`
- [ ] `mypy --strict` passes with zero errors on `app/`
- [ ] `ruff check .` passes with zero errors
- [ ] All tests pass: `uv run pytest --cov=app`
- [ ] Coverage ≥ 90% branches, functions, statements
- [ ] `openspec/specs/development_guide.md` updated with backend setup instructions
- [ ] `openspec/specs/api-spec.yml` BearerAuth description corrected to Auth0
