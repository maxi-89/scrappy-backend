# Data Model — Scrappy

## Overview

Scrappy uses **Supabase (PostgreSQL)** as its primary database. All tables follow a relational model with UUID primary keys, timestamptz timestamps, and snake_case naming.

> **Source of truth**: This file must be kept in sync with Alembic migrations and ORM models. Update it whenever a table, column, or index changes.

---

## Tables

### `businesses`

Raw scraped business records obtained from Google Maps.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `uuid` | PK, default `gen_random_uuid()` | Unique business record ID |
| `name` | `text` | NOT NULL | Business name |
| `category` | `text` | NOT NULL | Business category (e.g. `restaurants`, `clinics`) |
| `zone` | `text` | NOT NULL | Geographic zone (e.g. `CABA`, `Palermo`) |
| `address` | `text` | | Full address |
| `phone` | `text` | | Phone number |
| `website` | `text` | | Website URL |
| `google_maps_url` | `text` | | Google Maps listing URL |
| `rating` | `numeric(2,1)` | | Rating 0.0–5.0 |
| `review_count` | `integer` | default 0 | Number of Google reviews |
| `is_verified` | `boolean` | default false | Data quality flag |
| `scraped_at` | `timestamptz` | NOT NULL | When the record was scraped |
| `created_at` | `timestamptz` | NOT NULL, default `now()` | Record creation time |

**Indexes**: `category`, `zone`, `(category, zone)`

---

### `offers`

Admin-defined scraping offer categories available for purchase. Each offer represents a business category that users can order scraped data for.

> Prices are **not stored per offer** — they come from the global `pricing_config` table and vary by zone type (province or city).

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `uuid` | PK, default `gen_random_uuid()` | Offer ID |
| `category` | `text` | NOT NULL, UNIQUE | Category slug (e.g. `restaurants`, `clinics`) |
| `title` | `text` | NOT NULL | Display title (e.g. `"Restaurants"`) |
| `description` | `text` | | Markdown description shown to buyers |
| `is_active` | `boolean` | NOT NULL, default true | Visible to buyers only when true |
| `created_at` | `timestamptz` | NOT NULL, default `now()` | Creation timestamp |
| `updated_at` | `timestamptz` | NOT NULL, default `now()` | Last update timestamp |

**Indexes**: `category`, `is_active`

---

### `pricing_config`

Singleton table storing global pricing configuration. There is always exactly **one row** (`id = 1`).

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `integer` | PK, default 1 | Always 1 (singleton) |
| `price_province_usd` | `numeric(10,2)` | NOT NULL, CHECK > 0 | Price for province-level orders in USD |
| `price_city_usd` | `numeric(10,2)` | NOT NULL, CHECK > 0 | Price for city/locality-level orders in USD |
| `updated_at` | `timestamptz` | NOT NULL, default `now()` | Last update timestamp |

> Province orders are more expensive than city orders, as they cover a larger geographic area and produce more records.

---

### `orders`

Purchase records. Each order represents a single user-initiated scraping request for a specific offer, zone, and output format. One order = one scraping result.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `uuid` | PK, default `gen_random_uuid()` | Order ID |
| `user_id` | `uuid` | NOT NULL, FK → `users.id` | Buyer |
| `offer_id` | `uuid` | NOT NULL, FK → `offers.id` | Scraping offer (category) selected |
| `zone_type` | `text` | NOT NULL | `province` \| `city` |
| `zone_name` | `text` | NOT NULL | Name of the province or city (e.g. `"Buenos Aires"`, `"Córdoba"`) |
| `output_format` | `text` | NOT NULL | `csv` \| `xlsx` \| `json` |
| `price_usd` | `numeric(10,2)` | NOT NULL | Price snapshot at time of order (from `pricing_config`) |
| `status` | `text` | NOT NULL | `pending` \| `paid` \| `processing` \| `completed` \| `failed` \| `refunded` |
| `stripe_payment_intent_id` | `text` | UNIQUE | Stripe payment reference |
| `result_url` | `text` | | Storage URL of the generated result file (set when status = `completed`) |
| `email_sent_at` | `timestamptz` | | When the result email was sent to the user |
| `created_at` | `timestamptz` | NOT NULL, default `now()` | Order creation time |
| `paid_at` | `timestamptz` | | Payment confirmation time |

**Indexes**: `user_id`, `status`, `offer_id`

**Order status flow**:
```
pending → paid → processing → completed
                            → failed
       → refunded (from paid or completed)
```

---

### `scraping_jobs`

Tracks background scraping tasks. Each job is triggered automatically when an order is paid.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `uuid` | PK, default `gen_random_uuid()` | Job ID |
| `order_id` | `uuid` | NOT NULL, UNIQUE, FK → `orders.id` | Associated order (one job per order) |
| `category` | `text` | NOT NULL | Target category to scrape (copied from offer at job creation) |
| `zone` | `text` | NOT NULL | Full zone description (e.g. `"Buenos Aires province"`) |
| `status` | `text` | NOT NULL | `pending` \| `running` \| `completed` \| `failed` |
| `records_scraped` | `integer` | default 0 | Number of records collected |
| `error_message` | `text` | | Error details if failed |
| `started_at` | `timestamptz` | | When job started running |
| `finished_at` | `timestamptz` | | When job completed or failed |
| `created_at` | `timestamptz` | NOT NULL, default `now()` | Job creation time |

**Indexes**: `status`, `order_id`

---

### `users`

Registered buyers.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `uuid` | PK, default `gen_random_uuid()` | User ID (generated by the app) |
| `auth0_sub` | `text` | NOT NULL, UNIQUE | Auth0 subject identifier (e.g. `auth0|64abc...`) |
| `email` | `text` | NOT NULL, UNIQUE | User email |
| `full_name` | `text` | | Full name |
| `created_at` | `timestamptz` | NOT NULL, default `now()` | Registration timestamp |

**Indexes**: `auth0_sub`

> Auth is managed by **Auth0**. The `users` table stores application-level data.
> `auth0_sub` maps the Auth0 identity to the local record. It is synced automatically on the first authenticated request.

---

## Entity Relationships

```
pricing_config ─────────────────────────────── (singleton, no FK)

offers ◄──────────── orders ────────────► users
                        │
                   scraping_jobs
```

---

## Access Patterns

| Pattern | Table | Filter |
|---|---|---|
| List active offers | `offers` | `is_active = true` |
| Get offer by category slug | `offers` | `category = ?` |
| Get global pricing config | `pricing_config` | `id = 1` |
| Get orders for a user | `orders` | `user_id = ?` |
| Get order details (status polling) | `orders` | `id = ?` |
| Get scraping job for an order | `scraping_jobs` | `order_id = ?` |
| List all orders (admin) | `orders JOIN users JOIN offers` | status filter, pagination |
| List businesses by category+zone | `businesses` | `category = ? AND zone = ?` |

---

## Key Design Conventions

- All primary keys use **UUID** (`gen_random_uuid()`) except `pricing_config` which uses integer `1` (singleton)
- All tables include `created_at timestamptz NOT NULL DEFAULT now()`
- All mutable tables include `updated_at timestamptz NOT NULL DEFAULT now()` with an update trigger
- Snake_case for all table and column names
- Prices stored as `numeric(10,2)` — never float in financial columns
- Status fields use `text` with application-level enum validation (not PG enums, for easier migration)
- Foreign keys always define explicit `ON DELETE` behavior
- `result_url` stores the file storage URL (S3/Supabase Storage) after scraping completes
- Output files are generated on demand when the scraping job finishes; format matches `orders.output_format`
