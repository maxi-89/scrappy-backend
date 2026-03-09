# Scrappy Backend

NestJS REST API for Scrappy — an on-demand business data marketplace.

## Stack

- **NestJS 10** + TypeScript (strict)
- **Prisma 7** ORM → PostgreSQL (AWS RDS)
- **JWT** auth (access 15m + refresh 7d) + bcrypt
- **AWS SES** for transactional email
- **@vendia/serverless-express** → AWS Lambda
- **AWS SAM** for infrastructure (Lambda + API Gateway HTTP)

## Auth Endpoints

| Method | Path                    | Auth   | Description                    |
|--------|-------------------------|--------|--------------------------------|
| POST   | `/auth/signup`          | Public | Register (email + password)    |
| POST   | `/auth/login`           | Public | Login → access + refresh token |
| POST   | `/auth/logout`          | Bearer | Invalidate refresh token       |
| POST   | `/auth/refresh`         | —      | Rotate refresh → new pair      |
| POST   | `/auth/forgot-password` | Public | Send reset email via SES       |
| POST   | `/auth/reset-password`  | Public | Reset password with token      |

## Local Setup

### Prerequisites

- Node.js 20+
- PostgreSQL running locally (or AWS RDS URL)
- AWS credentials configured (for SES in dev)

### Install

```bash
npm install
```

### Configure

```bash
cp .env.example .env
# Fill in DATABASE_URL, JWT_SECRET, JWT_REFRESH_SECRET, SES_FROM_EMAIL, FRONTEND_URL
```

### Database

```bash
npx prisma migrate dev --name init
npx prisma generate
```

### Run

```bash
npm run start:dev
# API available at http://localhost:3000
```

## Tests

```bash
npm run test          # unit tests
npm run test:e2e      # e2e tests (requires test DB)
```

## Deploy to AWS

### 1. Create SSM Parameters

```bash
aws ssm put-parameter --name /scrappy/database-url \
  --value "postgresql://user:pass@host:5432/scrappy" --type SecureString

aws ssm put-parameter --name /scrappy/jwt-secret \
  --value "$(openssl rand -hex 32)" --type SecureString

aws ssm put-parameter --name /scrappy/jwt-refresh-secret \
  --value "$(openssl rand -hex 32)" --type SecureString

aws ssm put-parameter --name /scrappy/ses-from-email \
  --value "maxi.rodriguez.3105@gmail.com" --type String

aws ssm put-parameter --name /scrappy/frontend-url \
  --value "https://scrappy.io" --type String
```

### 2. Build and Deploy

```bash
sam build
sam deploy   # uses samconfig.toml
```

### 3. Run migrations against production DB

```bash
DATABASE_URL="postgresql://..." npx prisma migrate deploy
```

## Project Structure

```
src/
├── auth/           # Auth module (controller, service, DTOs, strategy, guard)
├── users/          # Users module (service, repository)
├── mail/           # Mail module (SES service)
├── prisma/         # PrismaService (global)
├── common/
│   └── filters/    # HttpExceptionFilter
├── app.module.ts
├── main.ts         # Local dev entry point
└── lambda.ts       # AWS Lambda handler
prisma/
└── schema.prisma   # Database schema
template.yaml       # AWS SAM definition
```

## Environment Variables

| Variable            | Required | Description                        |
|---------------------|----------|------------------------------------|
| DATABASE_URL        | Yes      | PostgreSQL connection string       |
| JWT_SECRET          | Yes      | Access token signing secret        |
| JWT_REFRESH_SECRET  | Yes      | Reserved for refresh token signing |
| SES_FROM_EMAIL      | Yes      | Verified SES sender address        |
| FRONTEND_URL        | Yes      | Used in password reset email link  |
| AWS_REGION          | No       | Default: us-east-1                 |
| PORT                | No       | Local dev port (default: 3000)     |
