# Backend Implementation Plan: SCRUM-8 — POST /admin/scraping-jobs

## Overview

Admin endpoint to create a scraping job record with status `pending` for a given category and zone. Returns 202 Accepted. The actual scraping is handled asynchronously (out of scope for this ticket — future work).

Requires the `X-Admin-Key` header for authorization.

**Layers involved**: Domain · Application · Infrastructure · Presentation
**DDD principles**: thin router, service orchestrates, repository isolates DB access, domain entity has invariants.

---

## Architecture Context

### Files to create

| File | Purpose |
|---|---|
| `app/domain/models/scraping_job.py` | `ScrapingJob` domain entity |
| `app/domain/repositories/i_scraping_job_repository.py` | Repository interface |
| `app/presentation/schemas/scraping_job_schemas.py` | Pydantic request/response schemas |
| `app/application/services/scraping_job_service.py` | Application service |
| `app/infrastructure/repositories/scraping_job_repository.py` | SQLAlchemy implementation |
| `app/presentation/routers/scraping_jobs_router.py` | FastAPI admin router |
| `tests/unit/domain/test_scraping_job.py` | Domain entity tests |
| `tests/unit/application/test_scraping_job_service.py` | Service tests |
| `tests/unit/presentation/test_scraping_jobs_router.py` | Router tests |

### Files to modify

| File | Change |
|---|---|
| `app/infrastructure/database/orm_models.py` | Add `ScrapingJobORM` |
| `app/infrastructure/dependencies.py` | Add `get_admin_key()` + `get_scraping_job_service()` |
| `main.py` | Register `/admin/scraping-jobs` router |
| `openspec/specs/data-model.md` | Make `order_id` nullable on `scraping_jobs` |
| `openspec/specs/api-spec.yml` | Add `POST /admin/scraping-jobs` back |

### Design note: `order_id` nullable

The updated `data-model.md` defined `order_id NOT NULL` on `scraping_jobs`. However, SCRUM-8 is an admin-triggered job with no associated order. The correct design is:

- `order_id` is **nullable** on `scraping_jobs`
- `NULL` = admin-triggered (manual, for data collection or testing)
- Non-NULL = auto-triggered by Stripe webhook (SCRUM-19, future)

This must be reflected in both `data-model.md` and the Alembic migration.

---

## Implementation Steps

### Step 0: Create Feature Branch

- **Branch name**: `feature/SCRUM-8-backend`
- From `main`:
  ```bash
  git checkout main
  git pull origin main
  git checkout -b feature/SCRUM-8-backend
  ```

---

### Step 1: Domain Entity

**File**: `app/domain/models/scraping_job.py`

Define a `@dataclass` with invariants:

```python
@dataclass
class ScrapingJob:
    id: str
    category: str
    zone: str
    status: str          # "pending" | "running" | "completed" | "failed"
    order_id: str | None
    records_scraped: int
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
```

`__post_init__` invariants:
- `category` must be non-empty (strip)
- `zone` must be non-empty (strip)
- `status` must be one of `{"pending", "running", "completed", "failed"}`
- `records_scraped` must be >= 0

---

### Step 2: Repository Interface

**File**: `app/domain/repositories/i_scraping_job_repository.py`

```python
class IScrapingJobRepository(ABC):
    @abstractmethod
    async def save(self, job: ScrapingJob) -> None: ...

    @abstractmethod
    async def find_by_id(self, job_id: str) -> ScrapingJob | None: ...

    @abstractmethod
    async def find_all(self, status: str | None = None) -> list[ScrapingJob]: ...
```

---

### Step 3: Pydantic Schemas

**File**: `app/presentation/schemas/scraping_job_schemas.py`

- **`CreateScrapingJobRequest`**: fields `category: str` (min 2, max 100) and `zone: str` (min 2, max 100)
- **`ScrapingJobResponse`**: all fields from the domain entity, `model_config = ConfigDict(from_attributes=True)`

---

### Step 4: Application Service

**File**: `app/application/services/scraping_job_service.py`

Single method `create_job(payload: CreateScrapingJobRequest) -> ScrapingJobResponse`:
1. Build `ScrapingJob` entity with `id=uuid4()`, `status="pending"`, `records_scraped=0`, `order_id=None`, all nullable timestamps = `None`, `created_at=datetime.now(UTC)`
2. Call `repository.save(job)`
3. Return `ScrapingJobResponse.model_validate(job.__dict__)`

No FastAPI, SQLAlchemy, or OS imports.

---

### Step 5: ORM Model + Migration

**File**: `app/infrastructure/database/orm_models.py` — add `ScrapingJobORM`:

```
__tablename__ = "scraping_jobs"

id          String PK
order_id    String nullable FK → orders.id (nullable — NULL for admin-triggered jobs)
category    String NOT NULL
zone        String NOT NULL
status      String NOT NULL, default "pending", index=True
records_scraped  Integer NOT NULL, default 0
error_message    String nullable
started_at       DateTime(timezone=True) nullable
finished_at      DateTime(timezone=True) nullable
created_at       DateTime(timezone=True) NOT NULL server_default=now()
```

**Note**: `order_id` is a FK to `orders.id`, but `nullable=True`. The `orders` table does not exist yet (future ticket). For now, define the column as `String nullable` **without the FK constraint** — the FK will be added in a future migration when `orders` is created. This avoids a missing-table dependency issue.

**Migration**:
```bash
uv run alembic revision --autogenerate -m "add scraping_jobs table"
```
Review the generated migration — confirm it creates the `scraping_jobs` table and that `order_id` has no FK constraint referencing `orders` yet.

---

### Step 6: SQLAlchemy Repository

**File**: `app/infrastructure/repositories/scraping_job_repository.py`

Implement `IScrapingJobRepository`:
- `save()`: add and commit the ORM row
- `find_by_id()`: select by PK, return `None` if not found
- `find_all(status=None)`: optional `WHERE status = ?` filter, no pagination needed for this ticket
- Private `_map_to_domain(row: ScrapingJobORM) -> ScrapingJob`

---

### Step 7: Dependency Injection

**File**: `app/infrastructure/dependencies.py` — add two new dependencies:

#### 7a. Admin key validation

```python
ADMIN_API_KEY = os.environ.get("ADMIN_API_KEY", "")

def get_admin_key(x_admin_key: str = Header(...)) -> str:
    if not ADMIN_API_KEY or x_admin_key != ADMIN_API_KEY:
        raise AppError("Invalid or missing admin key", status_code=401)
    return x_admin_key
```

Use `from fastapi import Header`.

#### 7b. Scraping job service

```python
def get_scraping_job_repository(session: AsyncSession = Depends(get_db_session)) -> IScrapingJobRepository:
    return ScrapingJobRepository(session)

def get_scraping_job_service(
    repository: IScrapingJobRepository = Depends(get_scraping_job_repository),
) -> ScrapingJobService:
    return ScrapingJobService(repository)
```

---

### Step 8: FastAPI Router

**File**: `app/presentation/routers/scraping_jobs_router.py`

```
router = APIRouter()

POST ""  → status_code=202
  - Depends(get_admin_key) for auth
  - Depends(get_scraping_job_service) for service
  - body: CreateScrapingJobRequest
  - calls service.create_job(payload)
  - returns ScrapingJobResponse
  - response_model=ScrapingJobResponse

GET ""   → list all, optional ?status= query param
  - Depends(get_admin_key)
  - returns list[ScrapingJobResponse]

GET "/{job_id}"
  - Depends(get_admin_key)
  - raises HTTPException 404 if not found
  - returns ScrapingJobResponse
```

No business logic. Only HTTP plumbing.

---

### Step 9: Register Router

**File**: `main.py`

```python
from app.presentation.routers import scraping_jobs_router

app.include_router(
    scraping_jobs_router.router,
    prefix="/admin/scraping-jobs",
    tags=["admin"],
)
```

---

### Step 10: Unit Tests

#### `tests/unit/domain/test_scraping_job.py`
- `test_valid_scraping_job_created_successfully`
- `test_empty_category_raises_value_error`
- `test_empty_zone_raises_value_error`
- `test_invalid_status_raises_value_error`
- `test_negative_records_scraped_raises_value_error`

#### `tests/unit/application/test_scraping_job_service.py`
- `test_create_job_saves_and_returns_response` — mock repo.save, verify returned fields (status=pending, category, zone)
- `test_create_job_generates_unique_id` — call service twice, verify different IDs
- `test_create_job_calls_repository_save_once`
- `test_list_jobs_delegates_to_repository`
- `test_get_job_returns_none_when_not_found`

#### `tests/unit/presentation/test_scraping_jobs_router.py`

Use `app.dependency_overrides` to mock:
- `get_admin_key` → returns `"test-key"` (always passes)
- `get_scraping_job_service` → returns `AsyncMock`

Test cases:
- `test_create_job_returns_202` — valid payload → 202 + response body
- `test_create_job_missing_category_returns_422` — Pydantic validation
- `test_create_job_missing_zone_returns_422`
- `test_create_job_without_admin_key_returns_401` — do NOT override `get_admin_key`, send wrong key
- `test_list_jobs_returns_200`
- `test_get_job_returns_404_when_not_found`

---

### Step 11: Update Documentation

- **`openspec/specs/data-model.md`**: Update `scraping_jobs.order_id` to be nullable; add note that `orders` FK will be added in future migration
- **`openspec/specs/api-spec.yml`**: Add `POST /admin/scraping-jobs` endpoint with `CreateScrapingJobRequest` / `ScrapingJobResponse` schemas (already defined in the spec)

---

## Implementation Order

1. Step 0 — Create branch `feature/SCRUM-8-backend`
2. Step 1 — Domain entity `ScrapingJob`
3. Step 2 — Repository interface `IScrapingJobRepository`
4. Step 3 — Pydantic schemas `scraping_job_schemas.py`
5. Step 4 — Application service `ScrapingJobService`
6. Step 5 — ORM model `ScrapingJobORM` + Alembic migration
7. Step 6 — SQLAlchemy repository `ScrapingJobRepository`
8. Step 7 — Dependencies: `get_admin_key` + `get_scraping_job_service`
9. Step 8 — FastAPI router `scraping_jobs_router.py`
10. Step 9 — Register router in `main.py`
11. Step 10 — Unit tests (all layers)
12. Step 11 — Update docs (`data-model.md`, `api-spec.yml`)

---

## Error Response Format

All errors: `{ "error": "message" }`

| Condition | Status |
|---|---|
| Missing or invalid `X-Admin-Key` | 401 |
| `category` or `zone` empty / too long | 422 (Pydantic) |
| Job not found (`GET /{job_id}`) | 404 |
| Internal error | 500 |

---

## Testing Checklist

- [ ] All happy-path cases covered
- [ ] All validation error cases covered (empty fields, missing header)
- [ ] 404 handled for `GET /{job_id}`
- [ ] Admin key auth tested both pass and fail
- [ ] Coverage threshold met (90%)
- [ ] Tests follow AAA pattern

---

## Dependencies

No new Python packages required. All dependencies already in `pyproject.toml`.

---

## Notes

- **No actual scraping logic** in this ticket. The job is created with `status = "pending"` and the scraping pipeline is a future implementation.
- **`order_id` nullable**: admin-triggered jobs have `order_id = None`. Order-triggered jobs (SCRUM-19) will set this FK at creation time.
- **No FK to `orders` yet**: the `orders` table does not exist. Add `order_id` as a plain nullable String column without a FK constraint. The FK will be added when `orders` is created (future migration).
- **`ADMIN_API_KEY` env var**: must be set in `.env` for local dev and in Lambda config for production.
- **`get_admin_key` uses `os.environ.get`**: use a module-level constant read at import time so it's testable. Tests override `ADMIN_API_KEY` by overriding the FastAPI dependency, not the env var.
- The router also implements `GET /admin/scraping-jobs` and `GET /admin/scraping-jobs/{job_id}` since they share the same admin auth pattern and repository.

---

## Implementation Verification

- [ ] Code follows DDD layered architecture
- [ ] No business logic in FastAPI routers
- [ ] No FastAPI/SQLAlchemy imports in application or domain layers
- [ ] mypy strict — no `Any`
- [ ] All tests pass (`uv run pytest`)
- [ ] Ruff passes (`uv run ruff check . --fix && uv run ruff format .`)
- [ ] Documentation updated (`data-model.md`, `api-spec.yml`)
