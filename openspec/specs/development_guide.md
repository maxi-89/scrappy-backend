# Guía de Desarrollo — Scrappy

Instrucciones para configurar y correr el proyecto localmente y desplegar a producción.

## Stack

### Backend
- **Runtime**: Node.js 22
- **Framework**: NestJS 11 + TypeScript (strict)
- **ORM**: Prisma 7 (adapter-pg)
- **Database**: PostgreSQL (AWS RDS)
- **Auth**: JWT (access 15m + refresh 7d) + bcrypt
- **Email**: AWS SES (`@aws-sdk/client-ses`)
- **Lambda adapter**: `@vendia/serverless-express`
- **Infra**: AWS SAM (Lambda nodejs22.x + API Gateway HTTP)
- **Tests**: Jest + Supertest

---

## Prerrequisitos

- Node.js 22+
- PostgreSQL corriendo localmente (o URL de AWS RDS)
- AWS CLI configurado (`aws configure`) — requerido para SES en desarrollo
- AWS SAM CLI (`pip install aws-sam-cli`)

---

## Backend

### 1. Instalar dependencias

```bash
cd scrappy-backend
npm install
```

### 2. Configurar variables de entorno

```bash
cp .env.example .env
```

Completar los valores en `.env`:

```env
# Base de datos
DATABASE_URL=postgresql://postgres:password@localhost:5432/scrappy

# JWT
JWT_SECRET=change-me-use-openssl-rand-hex-32
JWT_REFRESH_SECRET=change-me-use-openssl-rand-hex-32

# AWS SES
SES_FROM_EMAIL=tu-email@dominio.com
AWS_REGION=us-east-1

# Frontend (usado en el link del email de reset de contraseña)
FRONTEND_URL=http://localhost:3001

# Puerto local
PORT=3000
```

### 3. Base de datos

```bash
# Crear y aplicar migraciones
npx prisma migrate dev --name init

# Regenerar el cliente Prisma (tras cambios en schema.prisma)
npx prisma generate

# Abrir el browser visual de la DB
npx prisma studio
```

### 4. Desarrollo local

```bash
npm run start:dev
```

API disponible en: `http://localhost:3000`

### 5. Tests

```bash
npm run test          # Unit tests
npm run test:watch    # Watch mode
npm run test:cov      # Con reporte de cobertura
npm run test:e2e      # E2E tests (requiere DB de test)
```

### 6. Linting y formateo

```bash
npm run lint          # ESLint con auto-fix
npm run format        # Prettier
```

### 7. Build

```bash
npm run build         # Compila TypeScript → dist/
```

---

## Estructura del proyecto

```
src/
├── auth/             # Módulo de autenticación (controller, service, DTOs, strategy, guard)
├── users/            # Módulo de usuarios (service, repository)
├── mail/             # Módulo de email (servicio SES)
├── prisma/           # PrismaService + PrismaModule (global)
├── common/
│   └── filters/      # HttpExceptionFilter (global)
├── app.module.ts
├── main.ts           # Entry point para desarrollo local (puerto 3000)
└── lambda.ts         # Handler de AWS Lambda (con caché entre invocaciones warm)
prisma/
└── schema.prisma     # Esquema de base de datos
template.yaml         # Definición AWS SAM (Lambda + API Gateway)
samconfig.toml        # Configuración SAM (stack, región, capabilities)
```

---

## Deploy a AWS

El deploy automatizado se activa pusheando un tag de versión a `master`.

### Flujo de release

```bash
git tag v1.0.0
git push origin v1.0.0
```

El pipeline (`.github/workflows/deploy.yml`) corre dos jobs en secuencia:

1. **test** — ESLint + Jest (quality gate)
2. **deploy** — `npm run build` → `sam build` → `sam deploy`

### Setup inicial (una sola vez)

Ver [`openspec/specs/deploy-guide.md`](./deploy-guide.md) para las instrucciones completas de primer deploy.

En resumen, se necesita:

| Recurso | Descripción |
|---|---|
| AWS RDS PostgreSQL | Base de datos de producción |
| SSM Parameter Store | 5 parámetros `/scrappy/*` (database-url, jwt-secret, jwt-refresh-secret, ses-from-email, frontend-url) |
| Lambda `scrappy-api` | Creada por `sam deploy` |
| API Gateway HTTP API | Creada por `sam deploy` |
| IAM Role (OIDC) | Para GitHub Actions — permisos de Lambda + SAM S3 |
| GitHub Secret | `AWS_DEPLOY_ROLE_ARN` |

### Deploy manual de infraestructura

Cuando cambia `template.yaml`:

```bash
npm run build && sam build && sam deploy
```

### Migraciones en producción

Cuando hay nuevas migraciones:

```bash
DATABASE_URL="postgresql://user:pass@host:5432/scrappy" npx prisma migrate deploy
```

---

## Variables de entorno

| Variable | Local (`.env`) | Producción (SSM) | Descripción |
|---|---|---|---|
| `DATABASE_URL` | PostgreSQL local | `/scrappy/database-url` | Connection string de PostgreSQL |
| `JWT_SECRET` | String aleatorio | `/scrappy/jwt-secret` | Secret para firmar access tokens |
| `JWT_REFRESH_SECRET` | String aleatorio | `/scrappy/jwt-refresh-secret` | Reservado para futuro uso |
| `SES_FROM_EMAIL` | Email verificado | `/scrappy/ses-from-email` | Email remitente (SES) |
| `FRONTEND_URL` | `http://localhost:3001` | `/scrappy/frontend-url` | URL frontend (CORS + emails) |
| `AWS_REGION` | `us-east-1` | Lambda env | Región de AWS |
| `PORT` | `3000` | — | Solo para desarrollo local |

---

## Referencia de comandos

```bash
npm run start:dev          # Dev server con hot reload
npm run build              # Compilar TypeScript
npm run test               # Unit tests
npm run test:e2e           # E2E tests
npm run lint               # ESLint
npm run format             # Prettier
npx prisma migrate dev     # Crear y aplicar migración local
npx prisma migrate deploy  # Aplicar migraciones en producción
npx prisma studio          # UI visual de la DB
sam build                  # Empaquetar con esbuild
sam deploy                 # Desplegar a AWS
sam local start-api        # Simular Lambda localmente
```
