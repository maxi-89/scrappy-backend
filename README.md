# Scrappy Backend

FastAPI backend for the Scrappy on-demand business data marketplace. Runs on AWS Lambda via Mangum, with an async scraping pipeline powered by AWS Step Functions.

**Stack**: Python 3.12 · FastAPI · Pydantic v2 · SQLAlchemy 2.0 · Supabase (PostgreSQL) · AWS Lambda · AWS Step Functions · S3 · Stripe · Auth0 · pytest

---

## How it works

1. User browses **offers** (scraping packages by category) and selects a zone.
2. User creates an **order** → Stripe PaymentIntent is returned.
3. User completes payment → Stripe fires a webhook → order marked `paid`.
4. **Step Functions** scraping pipeline starts automatically:
   - `InitJob` → `ScrapeBusinesses` (Google Maps) → `NormalizeBusinesses` → `SaveBusinesses` → `Done`
   - On failure: `MarkFailed` updates order and job status.
5. Result file (CSV / Excel / JSON) is uploaded to S3. Order marked `completed`.
6. User downloads result via `GET /orders/{id}/download`.

---

## Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) — fast Python package manager
- [AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html) — for infrastructure deployment

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

---

## Setup

### 1. Install dependencies

```bash
uv sync
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | Yes | PostgreSQL connection string (`postgresql+asyncpg://...`) |
| `AUTH0_DOMAIN` | Yes | Auth0 tenant domain (e.g. `your-tenant.us.auth0.com`) |
| `AUTH0_AUDIENCE` | Yes | Auth0 API audience (e.g. `https://api.scrappy.io`) |
| `STRIPE_SECRET_KEY` | Yes | Stripe secret key (`sk_test_...` or `sk_live_...`) |
| `STRIPE_WEBHOOK_SECRET` | Yes | Stripe webhook signing secret (`whsec_...`) |
| `ADMIN_API_KEY` | Yes | Secret key for admin-only endpoints (`X-Admin-Key` header) |
| `GOOGLE_MAPS_API_KEY` | Yes | Google Maps API key for scraping |
| `STATE_MACHINE_ARN` | Yes | ARN of the Step Functions state machine (set after first deploy) |
| `RESULTS_BUCKET` | Yes | S3 bucket name for result files (set after first deploy) |
| `AWS_REGION` | No | AWS region (default: `us-east-1`) |
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

## API endpoints

### Public
| Method | Path | Description |
|---|---|---|
| `GET` | `/offers` | List active offers (optional `?zone=` for pricing) |
| `GET` | `/offers/{id}` | Get offer detail |

### Authenticated (Bearer token required)
| Method | Path | Description |
|---|---|---|
| `POST` | `/auth/sync` | Sync Auth0 user on first login |
| `POST` | `/orders` | Create order and get Stripe PaymentIntent |
| `GET` | `/orders` | List own orders |
| `GET` | `/orders/{id}` | Get order detail with scraping job status |
| `GET` | `/orders/{id}/download` | Download result file (CSV / Excel / JSON) |

### Webhooks
| Method | Path | Description |
|---|---|---|
| `POST` | `/webhooks/stripe` | Stripe webhook — confirms payment and triggers scraping |

### Admin (`X-Admin-Key` header required)
| Method | Path | Description |
|---|---|---|
| `POST` | `/admin/offers` | Create offer |
| `PATCH` | `/admin/offers/{id}` | Update offer |
| `DELETE` | `/admin/offers/{id}` | Delete offer |
| `GET` | `/admin/pricing` | List pricing entries |
| `PUT` | `/admin/pricing` | Upsert pricing entries (by zone) |
| `GET` | `/admin/orders` | List all orders (optional `?status=` filter) |
| `POST` | `/admin/scraping-jobs` | Trigger scraping job manually |
| `GET` | `/admin/scraping-jobs` | List scraping jobs (optional `?status=` filter) |
| `GET` | `/admin/scraping-jobs/{id}` | Get scraping job detail |

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

## Deploy to AWS

Infrastructure is defined in `template.yaml` (AWS SAM). It provisions:
- **API Lambda** — FastAPI + Mangum
- **5 scraping Lambdas** — Init, Scraper, Normalizer, Saver, MarkFailed
- **Step Functions state machine** — orchestrates the scraping pipeline
- **S3 bucket** — stores result files (30-day lifecycle)

All secrets are sourced from **AWS SSM Parameter Store** at deploy time (no env vars in the template).

### First deploy

```bash
sam build
sam deploy --guided
```

Follow the prompts. After deploy, copy the `STATE_MACHINE_ARN` and `RESULTS_BUCKET` outputs to your Lambda environment variables (and `.env` for local dev).

### Subsequent deploys

```bash
sam build && sam deploy
```

### Required SSM parameters

Create these in SSM Parameter Store before deploying:

| Parameter | Description |
|---|---|
| `/scrappy/database-url` | Supabase connection string |
| `/scrappy/admin-api-key` | Admin secret key |
| `/scrappy/auth0-domain` | Auth0 domain |
| `/scrappy/auth0-audience` | Auth0 audience |
| `/scrappy/stripe-secret-key` | Stripe secret key |
| `/scrappy/stripe-webhook-secret` | Stripe webhook secret |
| `/scrappy/google-maps-api-key` | Google Maps API key |

### CI/CD

Deployment is automated via **GitHub Actions** on every version tag pushed to `master`.

```bash
git tag v1.0.0 && git push origin v1.0.0
```

Required GitHub secret:

| Secret | Description |
|---|---|
| `AWS_DEPLOY_ROLE_ARN` | ARN of the IAM role for GitHub OIDC |

---

## Project structure

```
app/
├── domain/
│   ├── models/              # Domain entities (Order, Offer, Pricing, Business, ...)
│   └── repositories/        # Repository interfaces (ABCs)
├── application/
│   ├── services/            # OrderService, OfferService, PricingService, WebhookService, ...
│   └── workers/             # BusinessNormalizer, ScrapingWorker
├── infrastructure/
│   ├── database/            # SQLAlchemy session and ORM models
│   ├── auth/                # Auth0 JWT verifier
│   ├── aws/                 # S3Client, SfnClient
│   ├── stripe/              # StripeClient
│   ├── repositories/        # SQLAlchemy repository implementations
│   └── errors/              # AppError
└── presentation/
    ├── routers/             # FastAPI routers
    └── schemas/             # Pydantic request/response schemas
lambdas/                     # Step Functions Lambda handlers
statemachine/
│   └── scraping_workflow.asl.json   # Step Functions ASL definition
tests/
├── unit/
│   ├── domain/
│   ├── application/
│   ├── infrastructure/
│   ├── lambdas/
│   └── presentation/
alembic/                     # Database migrations
template.yaml                # AWS SAM infrastructure definition
samconfig.toml               # SAM deploy configuration
main.py                      # FastAPI app + Mangum Lambda handler
pyproject.toml
.env.example
```

---

For full setup including Supabase local dev and detailed deployment guide, see [`openspec/specs/development_guide.md`](./openspec/specs/development_guide.md).
