# Data Model — Scrappy

## Overview

Scrappy uses **PostgreSQL** (AWS RDS) as its primary database, managed via **Prisma ORM**.
All tables use UUID primary keys and camelCase field names in the Prisma schema.

---

## Tables

### User

Stores registered users with hashed passwords.

| Column         | Type      | Constraints           |
|----------------|-----------|-----------------------|
| id             | UUID      | PK, default uuid()    |
| email          | String    | UNIQUE, NOT NULL      |
| passwordHash   | String    | NOT NULL              |
| fullName       | String?   | nullable              |
| createdAt      | DateTime  | default now()         |
| updatedAt      | DateTime  | auto-updated          |

Relations: `refreshTokens []RefreshToken`, `passwordResetTokens []PasswordResetToken`

---

### RefreshToken

Stores opaque refresh tokens. Rotated on each use.

| Column    | Type     | Constraints           |
|-----------|----------|-----------------------|
| id        | UUID     | PK, default uuid()    |
| token     | String   | UNIQUE, NOT NULL      |
| userId    | String   | FK → User(id) CASCADE |
| expiresAt | DateTime | NOT NULL              |
| createdAt | DateTime | default now()         |

---

### PasswordResetToken

Stores one-time password reset tokens sent via email.

| Column    | Type      | Constraints           |
|-----------|-----------|-----------------------|
| id        | UUID      | PK, default uuid()    |
| token     | String    | UNIQUE, NOT NULL      |
| userId    | String    | FK → User(id) CASCADE |
| expiresAt | DateTime  | NOT NULL              |
| usedAt    | DateTime? | nullable (set on use) |
| createdAt | DateTime  | default now()         |

---

## Prisma Schema Location

`prisma/schema.prisma`

## Migration

```bash
npx prisma migrate dev --name <migration-name>
npx prisma migrate deploy   # production
```
