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

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | Yes | PostgreSQL connection string (`postgresql+asyncpg://...`) |
| `AUTH0_DOMAIN` | Yes | Auth0 tenant domain (e.g. `your-tenant.us.auth0.com`) |
| `AUTH0_AUDIENCE` | Yes | Auth0 API audience (e.g. `https://api.scrappy.io`) |
| `STRIPE_SECRET_KEY` | Yes (payments) | Stripe secret key (`sk_test_...` or `sk_live_...`) |
| `STRIPE_WEBHOOK_SECRET` | Yes (payments) | Stripe webhook signing secret (`whsec_...`) |
| `ADMIN_API_KEY` | Yes | Secret key for admin-only endpoints |
| `ENVIRONMENT` | No | `development` \| `production` (default: `development`) |

> Never commit `.env` to version control.

### 3. Apply database migrations

```bash
uv run alembic upgrade head
```

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

## Deploy to production

Deployment is fully automated via **GitHub Actions** on every version tag pushed to `master`.

### How it works

```
git tag v1.2.3 && git push origin v1.2.3
       │
       ▼
GitHub Actions: test → ruff → mypy → pytest
       │
       ▼
Docker build → push to Amazon ECR
       │
       ▼
aws lambda update-function-code
```

### Required GitHub secrets

Configure these in `Settings → Secrets and variables → Actions`:

| Secret | Description |
|---|---|
| `AWS_DEPLOY_ROLE_ARN` | ARN of the IAM role for GitHub OIDC (e.g. `arn:aws:iam::123456789:role/scrappy-deploy`) |

### Required AWS resources

Before the first deploy, create the following once (manually or via IaC):

#### 1. ECR repository

```bash
aws ecr create-repository \
  --repository-name scrappy-backend \
  --region us-east-1
```

#### 2. Lambda function (container image type)

Create the function in the AWS console or CLI pointing to the ECR image.
Set the handler to `main.handler`.

Lambda environment variables to configure:

| Variable | Value |
|---|---|
| `DATABASE_URL` | Supabase connection string |
| `AUTH0_DOMAIN` | Auth0 tenant domain |
| `AUTH0_AUDIENCE` | Auth0 API audience |
| `STRIPE_SECRET_KEY` | Stripe live secret key |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook secret |
| `ADMIN_API_KEY` | Admin secret key |
| `ENVIRONMENT` | `production` |

#### 3. IAM role for GitHub OIDC

The role must have:
- **Trust policy**: GitHub Actions OIDC provider (`token.actions.githubusercontent.com`) for this repo
- **Permissions**: `ecr:*` on the repository + `lambda:UpdateFunctionCode` + `lambda:GetFunction` on the function

#### 4. API Gateway

Create an HTTP API in API Gateway and integrate it with the Lambda function.
The function URL or API Gateway endpoint is the public URL of the backend.

### Triggering a deploy

```bash
# Tag the commit you want to release
git tag v1.0.0
git push origin v1.0.0
```

The pipeline runs automatically. Monitor progress in the **Actions** tab on GitHub.

---

## Project structure

```
app/
├── domain/
│   ├── models/              # Domain entities (user.py, ...)
│   └── repositories/        # Repository interfaces
├── application/
│   └── services/            # Application services
├── infrastructure/
│   ├── database/            # SQLAlchemy session and ORM models
│   ├── auth/                # Auth0 JWT verifier
│   ├── repositories/        # SQLAlchemy repository implementations
│   └── errors/              # AppError, DomainValidationError
└── presentation/
    ├── routers/             # FastAPI routers
    └── schemas/             # Pydantic I/O schemas
tests/
├── unit/
│   ├── domain/
│   ├── application/
│   └── presentation/
alembic/                     # Database migrations
.github/workflows/
│   └── deploy.yml           # CI/CD pipeline
main.py                      # FastAPI app + Mangum Lambda handler
Dockerfile                   # Lambda container image
pyproject.toml
.env.example
```

---

For full setup including Supabase local dev and detailed deployment guide, see [`openspec/specs/development_guide.md`](./openspec/specs/development_guide.md).
