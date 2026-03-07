# Scrappy Backend

FastAPI backend for the Scrappy business data marketplace. Runs on AWS Lambda via Mangum.

**Stack**: Python 3.12 · FastAPI · Pydantic v2 · SQLAlchemy 2.0 · Supabase (PostgreSQL) · pytest

---

## Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) — fast Python package manager

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

---

## Setup

### 1. Create virtual environment and install dependencies

```bash
uv sync
```

This creates a `.venv` folder and installs all dependencies (including dev) from `pyproject.toml`.

To activate the virtual environment manually:

```bash
source .venv/bin/activate
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` with your values:

```env
# Database
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:54322/postgres

# Auth0
AUTH0_DOMAIN=your-tenant.us.auth0.com
AUTH0_AUDIENCE=https://api.scrappy.io

# Environment
ENVIRONMENT=development
```

> Never commit `.env` to version control.

---

## Run locally

```bash
uv run uvicorn main:app --reload --port 8000
```

- API: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

---

## Tests

```bash
# Run all tests
uv run pytest

# With coverage report
uv run pytest --cov=app --cov-report=term-missing

# Unit tests only
uv run pytest tests/unit/
```

Coverage threshold: **90%**

---

## Linting and type checking

```bash
uv run ruff check . --fix
uv run ruff format .
uv run mypy app/
```

---

## Project structure

```
app/
├── domain/
│   └── models/              # Domain entities
├── application/
│   └── services/            # Application services
├── infrastructure/
│   ├── database/            # SQLAlchemy session and ORM models
│   ├── auth/                # Auth0 JWT verifier
│   └── errors/              # AppError, DomainValidationError
└── presentation/
    └── routers/             # FastAPI routers
tests/
├── unit/
│   ├── domain/
│   ├── infrastructure/
│   └── presentation/
main.py                      # FastAPI app + Mangum Lambda handler
pyproject.toml
.env.example
```

---

For full setup including Supabase and deployment, see [`openspec/specs/development_guide.md`](./openspec/specs/development_guide.md).
