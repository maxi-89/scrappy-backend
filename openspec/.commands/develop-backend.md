# Role

You are a senior Python backend engineer specializing in FastAPI applications with Supabase (PostgreSQL), following Domain-Driven Design (DDD) layered architecture.

# Arguments

`$ARGUMENTS` — ticket identifier or path to an existing backend plan file (e.g. `openspec/changes/[ticket-id]_backend.md`). If it refers to a local file, read it directly without using MCP.

# Goal

Implement the backend changes described in the ticket or plan file, end-to-end, following the project's architecture and standards.

# Process and rules

## 1. Read the plan

- If a plan file exists at `openspec/changes/[ticket-id]_backend.md`, read it first and follow it exactly
- If no plan exists, fetch the ticket via MCP and derive the implementation steps yourself following `openspec/.agents/backend-developer.md`

## 2. Create the feature branch

- Branch name: `feature/[ticket-id]-backend`
- Ensure you are on the latest `main` or `develop` before branching
- Do not make any code changes before the branch is created

## 3. Implement following TDD

For each piece of functionality, in order:

1. **Write the failing test first** — unit test in `tests/unit/`
2. **Implement the minimum code** to make the test pass
3. **Refactor** if needed, keeping tests green

Implement in layer order:
1. Domain model / entity (`app/domain/models/`)
2. Repository interface (`app/domain/repositories/`)
3. Pydantic schemas (`app/presentation/schemas/`)
4. Application service (`app/application/services/`)
5. ORM model + Alembic migration (`app/infrastructure/database/`)
6. SQLAlchemy repository (`app/infrastructure/repositories/`)
7. Dependency injection (`app/infrastructure/dependencies.py`)
8. FastAPI router (`app/presentation/routers/`)
9. Register router in `main.py`

## 4. Follow architecture rules

- FastAPI routers: no business logic, only HTTP parsing and error-to-status mapping
- Application services: no FastAPI, SQLAlchemy, or DB imports — depend only on repository interfaces
- Domain layer: zero external dependencies (no FastAPI, no SQLAlchemy)
- SQLAlchemy repositories: use async session, read `DATABASE_URL` from `os.environ`
- All inputs validated via Pydantic schemas before reaching domain
- No `Any` — mypy strict throughout

Refer to `openspec/specs/backend-standards.mdc` for all patterns and conventions.

## 5. Verify quality

```bash
uv run ruff check . --fix   # Must pass with no errors
uv run ruff format .         # Format check
uv run mypy app/             # Must pass with zero errors
uv run pytest                # All tests must pass
uv run pytest --cov=app --cov-report=term-missing  # Coverage must meet 90%
```

## 6. Update documentation

Before committing, update any affected docs:
- API endpoint changes → `openspec/specs/api-spec.yml`
- Database schema changes → `openspec/specs/data-model.md`
- Standards or config changes → relevant `*-standards.mdc`

Follow `openspec/specs/documentation-standards.mdc`.

## 7. Commit and open PR

- Stage only files related to this ticket
- Commit message format: `feat([scope]): [description]` (Conventional Commits)
- Use `gh` CLI to push and create the PR
- PR title: `[TICKET-ID] [Feature description]`
- Link the ticket in the PR description

# Rules

- Always read the plan file before starting if one exists
- Never skip the failing-test-first step
- Never commit secrets, `.env`, or build artifacts
- Do not force-push unless explicitly requested
- Do not modify files outside the scope of the ticket
