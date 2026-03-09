---
description: Development rules and guidelines for this project. Applicable to all AI agents.
alwaysApply: true
---

## 1. Core Principles

- **Small tasks, one at a time**: Always work in baby steps, one at a time. Never go forward more than one step.
- **Test-Driven Development**: Start with failing tests for any new functionality (TDD), according to the task details.
- **Type Safety**: All code must be fully typed. Use strict TypeScript.
- **Clear Naming**: Use clear, descriptive names for all variables and functions.
- **Incremental Changes**: Prefer incremental, focused changes over large, complex modifications.
- **Question Assumptions**: Always question assumptions and inferences.
- **Pattern Detection**: Detect and highlight repeated code patterns.

## 2. Language Standards

- **English Only**: All technical artifacts must always use English, including:
  - Code (variables, functions, classes, comments, error messages, log messages)
  - Documentation (README, guides, API docs)
  - Configuration files and scripts
  - Git commit messages
  - Test names and descriptions

## 3. Project Context

**Product**: Scrappy — an on-demand business data marketplace. Users purchase scraping jobs for a specific business category and geographic zone. After payment, scraping runs asynchronously and the result (CSV, Excel, or JSON) is available for download.

**Backend Stack**: NestJS 11 · TypeScript (strict) · Prisma 7 · PostgreSQL (AWS RDS) · JWT auth · AWS SES · @vendia/serverless-express

**Infrastructure**: AWS Lambda + API Gateway HTTP (SAM) · AWS RDS PostgreSQL · AWS SES

## 4. Key Commands

```bash
# Development
npm run start:dev          # Local dev server (port 3000)
npm run build              # Compile TypeScript

# Database
npx prisma generate        # Regenerate Prisma client
npx prisma migrate dev     # Create and run migration (local)
npx prisma migrate deploy  # Run pending migrations (production)
npx prisma studio          # Visual DB browser

# Tests
npm run test               # Unit tests
npm run test:e2e           # E2E tests

# Lambda / SAM
sam build                  # Build Lambda package
sam deploy                 # Deploy to AWS
sam local start-api        # Local Lambda simulation
```

## 5. Environment Variables

Copy `.env.example` to `.env` and fill in:

| Variable           | Description                        |
|--------------------|------------------------------------|
| DATABASE_URL       | PostgreSQL connection string       |
| JWT_SECRET         | Secret for signing access tokens   |
| JWT_REFRESH_SECRET | Secret for refresh token validation|
| SES_FROM_EMAIL     | Verified SES sender email          |
| FRONTEND_URL       | Frontend URL for reset email link  |
| AWS_REGION         | AWS region (default: us-east-1)    |

## 6. Specific Standards

For detailed standards refer to:

- [Backend Standards](./openspec/specs/backend-standards.mdc) — NestJS, Prisma, JWT, testing, error handling
- [API Spec](./openspec/specs/api-spec.yml) — OpenAPI 3.0 spec (source of truth for endpoints)
- [Data Model](./openspec/specs/data-model.md) — PostgreSQL schema (3 tables: User, RefreshToken, PasswordResetToken)
