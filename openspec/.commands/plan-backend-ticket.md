# Role

You are an expert software architect with deep experience in FastAPI applications with Python, applying Domain-Driven Design (DDD) with layered architecture (Domain, Application, Infrastructure, Presentation).

# Arguments

`$ARGUMENTS` — ticket identifier, ticket ID, or keywords. If it refers to a local file, read it directly without using MCP.

# Goal

Produce a step-by-step backend implementation plan for a ticket that is detailed enough for a developer to work end-to-end autonomously.

# Process and rules

1. Adopt the role defined in `openspec/.agents/backend-developer.md`
2. Fetch the ticket using the project management MCP. If `$ARGUMENTS` refers to a local file, read it directly
3. Propose a step-by-step plan for the backend, applying the standards in `openspec/specs`
4. Ensure the plan is complete enough that the developer needs no further clarification
5. Do not write implementation code — provide the plan only
6. If asked to start implementing, first move to the feature branch (Step 0) and follow `/develop-backend.md`

# Output format

Save the plan as a markdown document at `openspec/changes/[ticket-id]_backend.md`.

Use the following template:

---

## Template

### 1. Header
- Title: `# Backend Implementation Plan: [TICKET-ID] — [Feature Name]`

### 2. Overview
- Brief description of the feature
- Layers involved (Domain / Application / Infrastructure / Presentation)
- DDD and clean architecture principles applied

### 3. Architecture Context
- Files to create and files to modify
- Repository interfaces needed
- Dependencies between components

### 4. Implementation Steps

#### Step 0: Create Feature Branch
- **Action**: Create and switch to the feature branch
- **Branch name**: `feature/[ticket-id]-backend`
- **Steps**:
  1. Ensure you are on the latest `main` or `develop`
  2. `git pull origin [base-branch]`
  3. `git checkout -b feature/[ticket-id]-backend`
- **Note**: This must be the FIRST step before any code changes

#### Step 1: Domain Layer
- **File**: `app/domain/models/[entity].py`
- **Action**: Define the entity as a `@dataclass` with `__post_init__` invariants
- **Notes**: Zero dependencies on FastAPI, SQLAlchemy, or Supabase

#### Step 2: Repository Interface
- **File**: `app/domain/repositories/i_[entity]_repository.py`
- **Action**: Define the abstract repository contract (ABC + `@abstractmethod`)

#### Step 3: Pydantic Schemas
- **File**: `app/presentation/schemas/[entity]_schemas.py`
- **Action**: Define request schema (input validation via `Field`) and response schema (`ConfigDict(from_attributes=True)`)

#### Step 4: Application Service
- **File**: `app/application/services/[entity]_service.py`
- **Action**: Orchestrate domain logic — receive Pydantic input, build entity, call repository
- **Notes**: Must not import FastAPI, SQLAlchemy, or DB clients directly. Use constructor injection.

#### Step 5: ORM Model (if new table)
- **File**: `app/infrastructure/database/orm_models.py`
- **Action**: Add the SQLAlchemy ORM model extending `Base`
- **Migration**: Generate Alembic migration with `uv run alembic revision --autogenerate -m "..."`

#### Step 6: SQLAlchemy Repository
- **File**: `app/infrastructure/repositories/[entity]_repository.py`
- **Action**: Implement the repository interface using async SQLAlchemy session
- **Notes**: Map ORM rows to domain entities in a private `_map_to_domain()` method

#### Step 7: Dependency Injection
- **File**: `app/infrastructure/dependencies.py`
- **Action**: Add a `get_[entity]_service()` function using `Depends(get_db_session)`

#### Step 8: FastAPI Router
- **File**: `app/presentation/routers/[entity]_router.py`
- **Action**: Define route with `response_model`, inject service via `Depends`, raise `HTTPException` for HTTP-specific errors
- **Notes**: No business logic — only HTTP plumbing

#### Step 9: Register Router
- **File**: `main.py`
- **Action**: `app.include_router([entity]_router.router)`

#### Step 10: Unit Tests
- **Files**: `tests/unit/[layer]/test_[file].py`
- **Coverage required**: 90% branches, functions, statements
- **Cases to cover**:
  - Successful path
  - Validation errors (missing/invalid fields)
  - Not found (if applicable)
  - Repository/infrastructure errors
  - Edge cases specific to the business rule

#### Step N: Update Documentation
- **Action**: Review all changes and update affected docs
  - API changes → `openspec/specs/api-spec.yml`
  - Data model changes → `openspec/specs/data-model.md`
  - Standards/config changes → relevant `*-standards.mdc`
- Follow `openspec/specs/documentation-standards.mdc`
- **This step is MANDATORY** — do not skip it

---

### 5. Implementation Order
Numbered list from Step 0 (branch) to documentation update (always last)

### 6. Error Response Format
- JSON shape: `{ "error": "message" }`
- HTTP status code mapping for this feature

### 7. Testing Checklist
- [ ] All happy-path cases covered
- [ ] All validation error cases covered
- [ ] Infrastructure errors handled
- [ ] Coverage threshold met (90%)
- [ ] Tests follow AAA pattern

### 8. Dependencies
- New Python packages required (if any) with justification — add to `pyproject.toml`

### 9. Notes
- Business rules and constraints
- Assumptions made
- Environment variables required
- Anything the developer must know before starting

### 10. Implementation Verification
- [ ] Code follows DDD layered architecture
- [ ] No business logic in FastAPI routers
- [ ] No FastAPI/SQLAlchemy imports in application or domain layers
- [ ] mypy strict — no `Any`
- [ ] All tests pass (`uv run pytest`)
- [ ] Documentation updated
