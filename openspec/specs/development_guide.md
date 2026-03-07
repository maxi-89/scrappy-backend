# Development Guide — Scrappy

Step-by-step instructions to set up and run the project locally and deploy to production.

## Tech Stack

### Backend
- **Runtime**: Python 3.12
- **Framework**: FastAPI
- **ASGI Adapter**: Mangum (AWS Lambda)
- **Database**: Supabase (PostgreSQL via SQLAlchemy 2.0 async + asyncpg)
- **Validation**: Pydantic v2
- **Testing**: pytest + pytest-asyncio
- **Linting**: ruff + mypy
- **Dependency management**: uv (pyproject.toml)

### Frontend
- **Framework**: Next.js (App Router)
- **Language**: TypeScript (strict mode)
- **Styling**: Tailwind CSS
- **Testing**: Jest + React Testing Library / Playwright

### Infrastructure
- **Frontend**: Vercel
- **Backend**: AWS Lambda (via Mangum) + API Gateway
- **Database**: Supabase (managed PostgreSQL)
- **Payments**: Stripe

---

## Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) — `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Node.js 22+ and npm 10+
- AWS CLI configured (`aws configure`)
- Supabase CLI — `npm install -g supabase`
- A Supabase project (local or cloud)

---

## Backend

### 1. Install

```bash
cd scrappy/backend
uv sync
```

### 2. Environment Configuration

Copy `.env.example` to `.env` and fill in the values (never commit `.env`):

```bash
cp .env.example .env
```

```env
# Database
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:54322/postgres

# Auth0 (required from SCRUM-6 onwards)
AUTH0_DOMAIN=your-tenant.us.auth0.com
AUTH0_AUDIENCE=https://api.scrappy.io

# Stripe
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Admin
ADMIN_API_KEY=dev-admin-key-change-in-prod

# Environment
ENVIRONMENT=development
```

### 3. Local Supabase Setup

```bash
# Start local Supabase (Docker required)
supabase start

# Apply migrations
supabase db reset

# View local Studio at http://localhost:54323
```

### 4. Run Migrations

```bash
# Apply all migrations
uv run alembic upgrade head

# Generate a new migration after changing ORM models
uv run alembic revision --autogenerate -m "describe change"
```

### 5. Local Development

```bash
# Start FastAPI dev server with hot reload
uv run uvicorn main:app --reload --port 8000
```

- API available at: `http://localhost:8000`
- Interactive docs at: `http://localhost:8000/docs`
- ReDoc at: `http://localhost:8000/redoc`

### 6. Running Tests

```bash
# Run all tests
uv run pytest

# With coverage report
uv run pytest --cov=app --cov-report=term-missing

# Run only unit tests
uv run pytest tests/unit/

# Watch mode
uv run pytest --watch
```

Coverage threshold: **90%** for branches, functions, and statements.

### 7. Linting and Type Checking

```bash
# Lint and auto-fix
uv run ruff check . --fix
uv run ruff format .

# Type check
uv run mypy app/
```

### 8. Deploy to AWS Lambda

```bash
# Package and deploy (using AWS SAM or Serverless Framework)
uv run python scripts/build_lambda.py

# Or with Serverless Framework
npx serverless deploy --stage dev
```

After deploying, the CLI outputs the API Gateway endpoint URL.

### 9. Backend Project Structure

```
backend/
├── app/
│   ├── domain/
│   │   ├── models/              # Domain entities (dataset.py, business.py, order.py)
│   │   └── repositories/        # Repository interfaces (i_dataset_repository.py)
│   ├── application/
│   │   └── services/            # Application services (dataset_service.py)
│   ├── infrastructure/
│   │   ├── database/            # SQLAlchemy engine, session, ORM models
│   │   ├── repositories/        # Repository implementations
│   │   └── errors/              # AppError, DomainValidationError
│   └── presentation/
│       ├── routers/             # FastAPI routers (datasets_router.py)
│       └── schemas/             # Pydantic I/O schemas (dataset_schemas.py)
├── tests/
│   ├── unit/
│   │   ├── domain/
│   │   ├── application/
│   │   └── presentation/
│   └── integration/
├── alembic/                     # Database migrations
├── main.py                      # FastAPI app + Mangum Lambda handler
├── pyproject.toml
├── .env                         ← not committed
├── .env.example
├── .gitignore
└── Makefile
```

### 10. Makefile Reference

```bash
make dev          # Start FastAPI dev server
make test         # Run all tests
make test-cov     # Tests + coverage report
make lint         # ruff check + format
make typecheck    # mypy
make migrate      # alembic upgrade head
make db-reset     # supabase db reset
```

---

## Frontend

### 1. Install

```bash
cd scrappy/frontend
npm install
```

### 2. Environment Configuration

Create a `.env.local` file at the frontend root (never commit this file):

```env
# Backend API
NEXT_PUBLIC_API_URL=http://localhost:8000/v1
API_BASE_URL=http://localhost:8000/v1

# Supabase (public keys only)
NEXT_PUBLIC_SUPABASE_URL=http://localhost:54321
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-local-anon-key

# Stripe (public key only)
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_test_...
```

### 3. Local Development

```bash
npm run dev
```

- App available at: `http://localhost:3000`

### 4. Running Tests

```bash
npm test                  # Run unit tests
npm run test:watch        # Watch mode
npm run test:coverage     # With coverage report
npx playwright test       # Run E2E tests
```

### 5. Build and Deploy to Vercel

```bash
npm run build             # Build for production (CI check)
vercel --prod             # Deploy to Vercel (or push to main for auto-deploy)
```

### 6. Frontend Project Structure

```
frontend/
├── app/
│   ├── layout.tsx               # Root layout
│   ├── page.tsx                 # Home page (dataset marketplace)
│   ├── globals.css
│   ├── datasets/
│   │   ├── page.tsx             # Dataset listing page
│   │   └── [id]/
│   │       └── page.tsx         # Dataset detail + buy button
│   ├── orders/
│   │   ├── page.tsx             # User's order history
│   │   └── [id]/
│   │       └── page.tsx         # Order detail + download
│   └── (auth)/
│       ├── login/page.tsx
│       └── register/page.tsx
├── components/
│   ├── ui/                      # Button, Input, Card, Badge...
│   ├── datasets/                # DatasetCard, DatasetFilters, SampleDataTable
│   └── orders/                  # OrderSummary, DownloadButton
├── hooks/
│   ├── useDatasets.ts
│   └── useOrders.ts
├── lib/
│   ├── api/                     # datasetsApi.ts, ordersApi.ts
│   ├── supabase/                # Supabase client
│   └── utils/                   # cn.ts, formatCurrency.ts, formatDate.ts
├── types/                       # Dataset, Order, Business, User interfaces
├── e2e/                         # Playwright E2E tests
├── __tests__/
├── tailwind.config.ts
├── next.config.ts
├── tsconfig.json
├── .env.local                   ← not committed
├── .env.example
└── package.json
```

### 7. NPM Scripts Reference

```bash
npm run dev            # Start Next.js dev server
npm run build          # Build for production
npm start              # Start production server
npm test               # Run unit tests
npm run test:watch     # Tests in watch mode
npm run test:coverage  # Tests + coverage report
npm run lint           # Run ESLint
npx playwright test    # Run E2E tests
```

---

## OpenSpec Files

```
openspec/
├── specs/
│   ├── base-standards.mdc          # Core principles (all agents)
│   ├── backend-standards.mdc       # FastAPI, Python, Supabase standards
│   ├── frontend-standards.mdc      # Next.js App Router standards
│   ├── documentation-standards.mdc # Docs and AI spec maintenance rules
│   ├── api-spec.yml                # OpenAPI 3.0 spec (source of truth)
│   ├── data-model.md               # Supabase/PostgreSQL relational schema
│   └── development_guide.md        # This file
└── .commands/
    ├── plan-backend-ticket.md
    ├── plan-frontend-ticket.md
    ├── develop-backend.md
    ├── develop-frontend.md
    └── update-docs.md
```
