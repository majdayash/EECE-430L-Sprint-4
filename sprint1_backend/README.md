# backend_majdayash

A RESTful Flask backend for a USD/LBP currency exchange platform. Supports user authentication, real-time exchange rate tracking, a P2P marketplace, price alerts, wallet management, analytics, audit logging, and admin reporting.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Package Structure](#package-structure)
3. [Prerequisites](#prerequisites)
4. [Environment Setup](#environment-setup)
5. [Database Configuration](#database-configuration)
6. [Running the Server](#running-the-server)
7. [API Reference](#api-reference)
8. [Error Response Schema](#error-response-schema)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                    Flask Application                │
│                                                     │
│  ┌─────────┐  ┌──────────┐  ┌────────────────────┐ │
│  │  Routes │  │ JWT Auth │  │  Rate Limiter      │ │
│  │ (app.py)│  │Middleware│  │  (Flask-Limiter)   │ │
│  └────┬────┘  └──────────┘  └────────────────────┘ │
│       │                                             │
│  ┌────▼──────────────────────────────────────────┐  │
│  │            SQLAlchemy ORM Layer               │  │
│  │   (models: User, Transaction, Offer, …)       │  │
│  └────┬──────────────────────────────────────────┘  │
│       │                                             │
└───────┼─────────────────────────────────────────────┘
        │
   ┌────▼────┐
   │  MySQL  │
   └─────────┘
```

**Key design decisions:**

- Authentication uses **JWT Bearer tokens** (PyJWT). No session cookies.
- Every protected endpoint uses a `require_auth` decorator that decodes and validates the token.
- Admin-only endpoints additionally use a `require_role("ADMIN")` decorator.
- All error responses follow a **uniform JSON schema** — `{"error", "message", "status"}`.
- Rate limiting is applied globally at 60 requests/minute via Flask-Limiter (memory storage).
- CORS is pre-configured for common local frontend dev ports: 3000, 5173, 5500, 8080, 4200.
- Tables are created automatically on first startup via `db.create_all()` — no migrations needed.

---

## Package Structure

```
backend_majdayash/
│
├── app.py              # Flask application, all 45 route definitions,
│                       # JWT/RBAC decorators, global error handlers
├── db_config.py        # MySQL connection string (edit before running)
├── requirements.txt    # All Python dependencies
├── __init__.py
│
└── model/              # SQLAlchemy ORM models (one file per table)
    ├── user.py             # User — id, user_name, password_hashed, role, status
    ├── transaction.py      # Currency exchange record — amounts, direction, timestamp
    ├── offer.py            # P2P marketplace offer — from/to currency, amount, rate, status
    ├── trade.py            # Completed P2P trade — links offer + accepting user
    ├── alert.py            # Price threshold alert — direction, threshold, condition
    ├── notification.py     # In-app notification — type, message, read flag
    ├── watchlist_item.py   # Watchlist entry — user + currency pair
    ├── user_preference.py  # Per-user analytics/history defaults
    ├── wallet.py           # User USD/LBP balances
    ├── audit_log.py        # Immutable security audit trail
    ├── rate_source.py      # Source metadata attached to each submitted rate
    └── rate_anomaly.py     # Flagged outlier rate records
```

---

## Prerequisites

- **Python 3.9+**
- **MySQL 8.0+** running locally on port 3306

Verify:

```bash
python --version
mysql --version
```

---

## Environment Setup

### 1. Create and activate a virtual environment

From the repository root:

```bash
python -m venv venv
```

Activate:

- **Windows (PowerShell):** `.\venv\Scripts\Activate.ps1`
- **Windows (CMD):** `venv\Scripts\activate.bat`
- **macOS / Linux:** `source venv/bin/activate`

### 2. Install dependencies

```bash
pip install -r backend_majdayash/requirements.txt
```

### 3. Create a `.env` file

Create `.env` in the repository root (alongside the `backend_majdayash/` folder):

```env
SECRET_KEY=your-secret-key-here
JWT_SECRET_KEY=your-jwt-secret-here
```

Both values can be any long random string. If omitted the app falls back to `"dev-secret"`.

---

## Database Configuration

### 1. Create the MySQL database

```sql
CREATE DATABASE exchange CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 2. Set the connection string

Open `backend_majdayash/db_config.py` and update it with your MySQL credentials:

```python
DB_CONFIG = "mysql+pymysql://<user>:<password>@127.0.0.1:3306/exchange"
```

Replace `<user>` and `<password>` with your MySQL username and password.

### 3. Tables are auto-created

`db.create_all()` runs on startup and creates every table defined under `model/`. No migration scripts are required.

---

## Running the Server

From the repository root with the virtual environment active:

```bash
python -m flask --app backend_majdayash.app run
```

The server starts at **`http://127.0.0.1:5000`**.

Optional flags:

```bash
# Different port
python -m flask --app backend_majdayash.app run --port 8000

# Debug mode with hot-reload
python -m flask --app backend_majdayash.app run --debug
```

### Verify it is running

```bash
curl http://127.0.0.1:5000/exchangeRate
```

Expected response (when no transactions exist yet):

```json
{"usd_to_lbp": null, "lbp_to_usd": null}
```

---

## API Reference

All request and response bodies are JSON unless stated otherwise.

**Authentication header** (required on protected endpoints):
```
Authorization: Bearer <token>
```
Obtain a token via `POST /authentication`.

**Uniform error schema** (all error responses):
```json
{ "error": "Bad Request", "message": "usd_amount must be > 0", "status": 400 }
```

---

### POST /user — Register a new user

| | |
|---|---|
| **Auth** | No |
| **Rate limit** | None |

**Request body**

```json
{
  "user_name": "alice",
  "password": "secret123",
  "role": "USER"
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `user_name` | string | Yes | Must be unique, non-empty |
| `password` | string | Yes | Plain text, will be bcrypt-hashed |
| `role` | string | No | `"USER"` (default) or `"ADMIN"` |

**Response 201**

```json
{
  "id": 1,
  "user_name": "alice",
  "role": "USER",
  "status": "ACTIVE",
  "created_at": "2026-02-22T10:00:00"
}
```

**Error responses**

| Code | Condition |
|------|-----------|
| 400 | Missing `user_name` or `password`; empty string; invalid `role` |
| 409 | `user_name` already taken |

---

### POST /authentication — Log in and receive a JWT

| | |
|---|---|
| **Auth** | No |
| **Rate limit** | 5 per minute |

**Request body**

```json
{ "user_name": "alice", "password": "secret123" }
```

**Response 200**

```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "id": 1,
    "user_name": "alice",
    "role": "USER",
    "status": "ACTIVE",
    "created_at": "2026-02-22T10:00:00"
  }
}
```

**Error responses**

| Code | Condition |
|------|-----------|
| 400 | Missing `user_name` or `password` field |
| 401 | Account is banned |
| 403 | Wrong password or unknown username |
| 429 | Rate limit exceeded |

---

### POST /transaction — Submit a currency exchange transaction

| | |
|---|---|
| **Auth** | Yes |
| **Rate limit** | 5 per minute |

**Request body**

```json
{
  "usd_amount": 100,
  "lbp_amount": 89500,
  "transaction_type": "usd-to-lbp"
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `usd_amount` | number | Yes | Must be > 0 |
| `lbp_amount` | number | Yes | Must be > 0 |
| `transaction_type` | string | Yes | `"usd-to-lbp"` or `"lbp-to-usd"` |

**Response 201**

```json
{
  "ok": true,
  "transaction": {
    "id": 42,
    "usd_amount": 100.0,
    "lbp_amount": 89500.0,
    "usd_to_lbp": true,
    "user_id": 1,
    "added_date": "2026-02-22T10:05:00"
  }
}
```

**Error responses**

| Code | Condition |
|------|-----------|
| 400 | Missing/invalid amounts or direction; rate deviates >20% from recent average (outlier detected); insufficient wallet balance |
| 401 | Missing or invalid token |
| 429 | Rate limit exceeded |

---

### GET /transaction — List caller's transactions

| | |
|---|---|
| **Auth** | Yes |
| **Rate limit** | None |

No request body. No query parameters.

**Response 200**

```json
[
  {
    "id": 42,
    "usd_amount": 100.0,
    "lbp_amount": 89500.0,
    "usd_to_lbp": true,
    "user_id": 1,
    "added_date": "2026-02-22T10:05:00"
  }
]
```

**Error responses**

| Code | Condition |
|------|-----------|
| 401 | Missing or invalid token |

---

### GET /transactions/export — Download transactions as CSV

| | |
|---|---|
| **Auth** | Yes |
| **Rate limit** | None |

**Query parameters** (all optional)

| Parameter | Example | Description |
|-----------|---------|-------------|
| `from` | `2026-01-01` | ISO 8601 start date |
| `to` | `2026-02-01` | ISO 8601 end date (inclusive) |

**Response 200** — `Content-Type: text/csv`, `Content-Disposition: attachment; filename="transactions.csv"`

```
ID,USD Amount,LBP Amount,Direction,Date,Exchange Rate
42,100.00,89500.00,USD→LBP,2026-02-22 10:05:00,895.00
```

**Error responses**

| Code | Condition |
|------|-----------|
| 400 | `from` or `to` cannot be parsed as a date |
| 401 | Missing or invalid token |

---

### GET /exchangeRate — Current buy/sell rates

| | |
|---|---|
| **Auth** | No |
| **Rate limit** | None |

No request body. No query parameters.

Computes volume-weighted averages from all transactions in the last **72 hours**. Returns `null` when no transactions exist for a direction.

**Response 200**

```json
{
  "usd_to_lbp": 89500.0,
  "lbp_to_usd": 89000.0,
  "buy_usd": 89000.0,
  "sell_usd": 89500.0
}
```

(`buy_usd` = `lbp_to_usd`, `sell_usd` = `usd_to_lbp` — both aliases are returned for compatibility.)

**Error responses**

None — always returns 200; missing-data directions are `null`.

---

### GET /history/rate — Time-series exchange rate history

| | |
|---|---|
| **Auth** | Yes |
| **Rate limit** | None |

**Query parameters** (fall back to saved user preferences when omitted)

| Parameter | Example | Description |
|-----------|---------|-------------|
| `from` | `2026-02-01T00:00:00` | ISO 8601 start datetime |
| `to` | `2026-02-22T23:59:59` | ISO 8601 end datetime |
| `interval` | `hour` or `day` | Bucket size |

**Response 200**

```json
[
  {
    "timestamp": "2026-02-22T10:00:00",
    "avg_rate": 89500.0,
    "min_rate": 89200.0,
    "max_rate": 89800.0,
    "count": 5
  }
]
```

**Error responses**

| Code | Condition |
|------|-----------|
| 400 | Unparseable date; invalid `interval` value; `from` >= `to` |
| 401 | Missing or invalid token |
| 404 | No transactions exist in the requested range |

---

### GET /analytics/rate — Aggregated rate statistics

| | |
|---|---|
| **Auth** | Yes |
| **Rate limit** | None |

**Query parameters** (fall back to saved user preferences when omitted)

| Parameter | Example | Description |
|-----------|---------|-------------|
| `from` | `2026-02-01T00:00:00` | ISO 8601 start datetime |
| `to` | `2026-02-22T23:59:59` | ISO 8601 end datetime |
| `direction` | `USD_LBP` or `LBP_USD` | Exchange direction to analyse |

**Response 200**

```json
{
  "min": 88000.0,
  "max": 91000.0,
  "avg": 89500.0,
  "count": 12,
  "percentage_change": 1.5,
  "volatility": 300.5,
  "trend": "up"
}
```

`trend` is `"up"`, `"down"`, or `"flat"` (< 1% change).

**Error responses**

| Code | Condition |
|------|-----------|
| 400 | Unparseable date; invalid `direction`; `from` >= `to` |
| 401 | Missing or invalid token |
| 404 | No transactions in the requested range for that direction |

---

### POST /market/offers — Post a P2P exchange offer

| | |
|---|---|
| **Auth** | Yes |
| **Rate limit** | None |

**Request body**

```json
{
  "from_currency": "USD",
  "to_currency": "LBP",
  "amount_from": 100,
  "rate": 89500
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `from_currency` | string | Yes | `"USD"` or `"LBP"` |
| `to_currency` | string | Yes | `"USD"` or `"LBP"`, must differ from `from_currency` |
| `amount_from` | number | Yes | Amount being offered (must be > 0) |
| `rate` | number | Yes | LBP per USD (must be > 0) |

**Response 201**

```json
{
  "id": 7,
  "creator_user_id": 1,
  "from_currency": "USD",
  "to_currency": "LBP",
  "amount_from": 100.0,
  "rate": 89500.0,
  "status": "OPEN",
  "created_at": "2026-02-22T11:00:00",
  "updated_at": null
}
```

**Error responses**

| Code | Condition |
|------|-----------|
| 400 | Missing required field; same currencies; non-positive amounts |
| 401 | Missing or invalid token |

---

### GET /market/offers — Browse open offers

| | |
|---|---|
| **Auth** | Yes |
| **Rate limit** | None |

**Query parameters** (all optional)

| Parameter | Example | Description |
|-----------|---------|-------------|
| `from_currency` | `USD` | Filter by source currency |
| `to_currency` | `LBP` | Filter by target currency |

**Response 200** — array of offer objects (same schema as POST response), `status` always `"OPEN"`.

**Error responses**

| Code | Condition |
|------|-----------|
| 400 | Invalid currency value in filter |
| 401 | Missing or invalid token |

---

### POST /market/offers/\<offer_id\>/accept — Accept an offer

| | |
|---|---|
| **Auth** | Yes |
| **Rate limit** | 5 per minute |

No request body.

Atomically: marks the offer as `ACCEPTED`, creates a Trade record, transfers wallet funds between buyer and seller.

**Response 200**

```json
{
  "id": 7,
  "status": "ACCEPTED",
  "trade_id": 3,
  ...
}
```

**Error responses**

| Code | Condition |
|------|-----------|
| 400 | Offer is not `OPEN`; caller is the offer creator; insufficient wallet balance for buyer or seller |
| 401 | Missing or invalid token |
| 404 | Offer not found |
| 429 | Rate limit exceeded |

---

### POST /market/offers/\<offer_id\>/cancel — Cancel an offer

| | |
|---|---|
| **Auth** | Yes |
| **Rate limit** | None |

No request body.

**Response 200** — updated offer object with `"status": "CANCELED"`.

**Error responses**

| Code | Condition |
|------|-----------|
| 400 | Offer is not `OPEN` |
| 401 | Missing or invalid token |
| 403 | Caller is not the offer creator |
| 404 | Offer not found |

---

### GET /market/me/offers — My posted offers

| | |
|---|---|
| **Auth** | Yes |
| **Rate limit** | None |

No request body. Returns offers in all statuses, newest first.

**Response 200** — array of offer objects.

**Error responses**

| Code | Condition |
|------|-----------|
| 401 | Missing or invalid token |

---

### GET /market/me/trades — My completed trades

| | |
|---|---|
| **Auth** | Yes |
| **Rate limit** | None |

No request body. Returns trades where the caller was buyer or seller, newest first.

**Response 200**

```json
[
  {
    "id": 3,
    "offer_id": 7,
    "buyer_user_id": 2,
    "seller_user_id": 1,
    "from_currency": "USD",
    "to_currency": "LBP",
    "amount_from": 100.0,
    "rate": 89500.0,
    "executed_at": "2026-02-22T11:05:00"
  }
]
```

**Error responses**

| Code | Condition |
|------|-----------|
| 401 | Missing or invalid token |

---

### POST /alerts — Create a price threshold alert

| | |
|---|---|
| **Auth** | Yes |
| **Rate limit** | None |

**Request body**

```json
{
  "direction": "USD_LBP",
  "threshold": 90000,
  "condition": "ABOVE"
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `direction` | string | Yes | `"USD_LBP"` or `"LBP_USD"` |
| `threshold` | number | Yes | Must be > 0 |
| `condition` | string | Yes | `"ABOVE"` or `"BELOW"` |

**Response 201**

```json
{
  "id": 5,
  "user_id": 1,
  "direction": "USD_LBP",
  "threshold": 90000.0,
  "condition": "ABOVE",
  "triggered": false,
  "triggered_at": null,
  "created_at": "2026-02-22T12:00:00"
}
```

**Error responses**

| Code | Condition |
|------|-----------|
| 400 | Invalid `direction` or `condition`; missing or non-positive `threshold` |
| 401 | Missing or invalid token |

---

### GET /alerts — List caller's alerts

| | |
|---|---|
| **Auth** | Yes |
| **Rate limit** | None |

No request body. Returns alerts newest first.

**Response 200** — array of alert objects (same schema as POST response).

**Error responses**

| Code | Condition |
|------|-----------|
| 401 | Missing or invalid token |

---

### DELETE /alerts/\<alert_id\> — Delete an alert

| | |
|---|---|
| **Auth** | Yes |
| **Rate limit** | None |

No request body.

**Response 200**

```json
{ "message": "Alert deleted successfully" }
```

**Error responses**

| Code | Condition |
|------|-----------|
| 401 | Missing or invalid token |
| 403 | Alert belongs to a different user |
| 404 | Alert not found |

---

### GET /notifications — List caller's notifications

| | |
|---|---|
| **Auth** | Yes |
| **Rate limit** | None |

**Query parameters** (all optional)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `unread` | `false` | Set to `true` to return only unread notifications |
| `limit` | `50` | Max records (capped at 200) |
| `offset` | `0` | Pagination offset |

**Response 200**

```json
[
  {
    "id": 12,
    "user_id": 1,
    "type": "trade_completed",
    "message": "Your offer #7 was accepted and a trade was completed",
    "metadata": {"offer_id": 7, "trade_id": 3, "role": "creator"},
    "read_at": null,
    "created_at": "2026-02-22T11:05:00"
  }
]
```

**Error responses**

| Code | Condition |
|------|-----------|
| 401 | Missing or invalid token |

---

### PATCH /notifications/\<notification_id\>/read — Mark as read

| | |
|---|---|
| **Auth** | Yes |
| **Rate limit** | None |

No request body. Sets `read_at` to the current timestamp.

**Response 200** — updated notification object.

**Error responses**

| Code | Condition |
|------|-----------|
| 401 | Missing or invalid token |
| 403 | Notification belongs to a different user |
| 404 | Notification not found |

---

### DELETE /notifications/\<notification_id\> — Delete a notification

| | |
|---|---|
| **Auth** | Yes |
| **Rate limit** | None |

No request body.

**Response 200**

```json
{ "message": "Notification deleted successfully" }
```

**Error responses**

| Code | Condition |
|------|-----------|
| 401 | Missing or invalid token |
| 403 | Notification belongs to a different user |
| 404 | Notification not found |

---

### POST /watchlist — Add a watchlist item

| | |
|---|---|
| **Auth** | Yes |
| **Rate limit** | None |

**Request body**

```json
{
  "type": "rate_threshold",
  "payload_json": { "direction": "USD_LBP", "threshold": 90000 }
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `type` | string | Yes | Non-empty label for the item (e.g. `"rate_threshold"`) |
| `payload_json` | object or JSON string | Yes | Arbitrary payload; canonicalized for duplicate detection |

**Response 201**

```json
{
  "id": 3,
  "user_id": 1,
  "type": "rate_threshold",
  "payload_json": "{\"direction\": \"USD_LBP\", \"threshold\": 90000}",
  "created_at": "2026-02-22T13:00:00"
}
```

**Error responses**

| Code | Condition |
|------|-----------|
| 400 | Missing `type` or `payload_json`; `payload_json` is not valid JSON |
| 401 | Missing or invalid token |
| 409 | Identical watchlist item already exists for this user |

---

### GET /watchlist — List caller's watchlist

| | |
|---|---|
| **Auth** | Yes |
| **Rate limit** | None |

No request body. Returns items newest first.

**Response 200** — array of watchlist item objects (same schema as POST response).

**Error responses**

| Code | Condition |
|------|-----------|
| 401 | Missing or invalid token |

---

### DELETE /watchlist/\<item_id\> — Remove a watchlist item

| | |
|---|---|
| **Auth** | Yes |
| **Rate limit** | None |

No request body.

**Response 200**

```json
{ "message": "Watchlist item deleted successfully" }
```

**Error responses**

| Code | Condition |
|------|-----------|
| 401 | Missing or invalid token |
| 403 | Item belongs to a different user |
| 404 | Item not found |

---

### GET /preferences — Get analytics/history defaults

| | |
|---|---|
| **Auth** | Yes |
| **Rate limit** | None |

No request body. Creates a row with defaults if none exists yet.

**Response 200**

```json
{
  "user_id": 1,
  "default_from_range_hours": 24,
  "default_interval": "hour",
  "default_direction": "USD_LBP",
  "updated_at": null
}
```

**Error responses**

| Code | Condition |
|------|-----------|
| 401 | Missing or invalid token |

---

### PUT /preferences — Update analytics/history defaults

| | |
|---|---|
| **Auth** | Yes |
| **Rate limit** | None |

**Request body** (all fields optional — only supplied keys are updated)

```json
{
  "default_from_range_hours": 72,
  "default_interval": "day",
  "default_direction": "LBP_USD"
}
```

| Field | Valid values |
|-------|-------------|
| `default_from_range_hours` | Positive integer, max 8760 (1 year) |
| `default_interval` | `"hour"` or `"day"` |
| `default_direction` | `"USD_LBP"` or `"LBP_USD"` |

**Response 200** — updated preferences object.

**Error responses**

| Code | Condition |
|------|-----------|
| 400 | Invalid value for any field |
| 401 | Missing or invalid token |

---

### GET /wallet — Get caller's wallet balances

| | |
|---|---|
| **Auth** | Yes |
| **Rate limit** | None |

No request body. Creates a zero-balance wallet if none exists.

**Response 200**

```json
{
  "user_id": 1,
  "usd_balance": 500.0,
  "lbp_balance": 44750000.0,
  "created_at": "2026-02-20T09:00:00",
  "updated_at": "2026-02-22T11:05:00"
}
```

**Error responses**

| Code | Condition |
|------|-----------|
| 401 | Missing or invalid token |

---

### PUT /wallet — Set wallet balances

| | |
|---|---|
| **Auth** | Yes |
| **Rate limit** | None |

**Request body** (all fields optional)

```json
{ "usd_balance": 500.0, "lbp_balance": 1000000.0 }
```

Neither balance may be negative.

**Response 200** — updated wallet object.

**Error responses**

| Code | Condition |
|------|-----------|
| 400 | Non-numeric value; negative balance |
| 401 | Missing or invalid token |

---

### GET /wallet/user/\<user_id\> — Get wallet by user ID

| | |
|---|---|
| **Auth** | Yes |
| **Rate limit** | None |

No request body. Creates a zero-balance wallet if none exists for the given user.

**Response 200** — wallet object for that user.

**Error responses**

| Code | Condition |
|------|-----------|
| 401 | Missing or invalid token |

---

### GET /me/audit — Caller's audit log entries

| | |
|---|---|
| **Auth** | Yes |
| **Rate limit** | None |

**Query parameters** (all optional)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `limit` | `100` | Max records (capped at 500) |
| `offset` | `0` | Pagination offset |
| `event_type` | — | Filter by type (e.g. `login_attempt`, `transaction_submitted`) |

**Response 200**

```json
[
  {
    "id": 100,
    "user_id": 1,
    "event_type": "login_attempt",
    "success": true,
    "metadata": {"user_name": "alice"},
    "created_at": "2026-02-22T10:00:00"
  }
]
```

**Error responses**

| Code | Condition |
|------|-----------|
| 401 | Missing or invalid token |

---

### GET /admin/users — List all users *(Admin)*

| | |
|---|---|
| **Auth** | Admin JWT |
| **Rate limit** | None |

No request body.

**Response 200**

```json
[
  { "id": 1, "user_name": "alice", "role": "USER", "status": "ACTIVE", "created_at": "2026-02-20T09:00:00" },
  { "id": 2, "user_name": "bob",   "role": "ADMIN","status": "ACTIVE", "created_at": "2026-02-20T09:01:00" }
]
```

**Error responses**

| Code | Condition |
|------|-----------|
| 401 | Missing or invalid token |
| 403 | Caller is not ADMIN |

---

### PATCH /admin/users/\<user_id\>/status — Change user account status *(Admin)*

| | |
|---|---|
| **Auth** | Admin JWT |
| **Rate limit** | None |

**Request body**

```json
{ "status": "BANNED" }
```

Valid values: `"ACTIVE"`, `"SUSPENDED"`, `"BANNED"`.

**Response 200** — updated user summary object.

**Error responses**

| Code | Condition |
|------|-----------|
| 400 | Missing `status` or invalid value |
| 401 | Missing or invalid token |
| 403 | Caller is not ADMIN |
| 404 | User not found |

---

### GET /admin/stats/transactions — Platform-wide transaction stats *(Admin)*

| | |
|---|---|
| **Auth** | Admin JWT |
| **Rate limit** | None |

No request body.

**Response 200**

```json
{
  "total_transactions": 500,
  "usd_to_lbp_count": 320,
  "lbp_to_usd_count": 180,
  "usd_to_lbp_volume_usd": 32000.0,
  "lbp_to_usd_volume_usd": 18000.0,
  "unique_users": 45,
  "earliest_transaction": "2026-01-01T08:00:00",
  "latest_transaction": "2026-02-22T11:05:00"
}
```

**Error responses**

| Code | Condition |
|------|-----------|
| 401 | Missing or invalid token |
| 403 | Caller is not ADMIN |

---

### GET /admin/audit — All users' audit logs *(Admin)*

| | |
|---|---|
| **Auth** | Admin JWT |
| **Rate limit** | None |

**Query parameters** (all optional)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `limit` | `100` | Max records (capped at 1000) |
| `offset` | `0` | Pagination offset |
| `event_type` | — | Filter by event type |
| `user_id` | — | Filter by user ID |
| `success` | — | `true` or `false` |

**Response 200** — array of audit log objects (same schema as `GET /me/audit`).

**Error responses**

| Code | Condition |
|------|-----------|
| 401 | Missing or invalid token |
| 403 | Caller is not ADMIN |

---

### GET /admin/rate/quality — Rate quality dashboard *(Admin)*

| | |
|---|---|
| **Auth** | Admin JWT |
| **Rate limit** | None |

**Query parameters** (optional): `limit` — number of recent anomalies (default 20, max 100).

**Response 200**

```json
{
  "sources_summary": [
    { "source": "INTERNAL_COMPUTED", "count": 500, "avg_rate": 89450.0 }
  ],
  "anomalies": {
    "recent": [
      {
        "id": 1,
        "direction": "USD_LBP",
        "previous_rate": 89500.0,
        "new_rate": 110000.0,
        "percent_change": 22.9,
        "time_diff_minutes": 2.5,
        "reason": "Rate deviation exceeds 20%",
        "flagged_at": "2026-02-22T10:30:00"
      }
    ],
    "total_count": 3,
    "last_24h_count": 1
  },
  "thresholds": {
    "percent_change": 20,
    "time_window_minutes": 180
  }
}
```

**Error responses**

| Code | Condition |
|------|-----------|
| 401 | Missing or invalid token |
| 403 | Caller is not ADMIN |

---

### GET /admin/users/\<user_id\>/preferences — Read any user's preferences *(Admin)*

| | |
|---|---|
| **Auth** | Admin JWT |
| **Rate limit** | None |

No request body. Creates default preferences if none exist.

**Response 200** — preference object (same schema as `GET /preferences`).

**Error responses**

| Code | Condition |
|------|-----------|
| 401 | Missing or invalid token |
| 403 | Caller is not ADMIN |
| 404 | User not found |

---

### PUT /admin/users/\<user_id\>/preferences — Update any user's preferences *(Admin)*

| | |
|---|---|
| **Auth** | Admin JWT |
| **Rate limit** | None |

Same request body as `PUT /preferences`.

**Response 200** — updated preference object.

**Error responses**

| Code | Condition |
|------|-----------|
| 400 | Invalid field value |
| 401 | Missing or invalid token |
| 403 | Caller is not ADMIN |
| 404 | User not found |

---

### GET /admin/users/\<user_id\>/alerts — List a user's alerts *(Admin)*

| | |
|---|---|
| **Auth** | Admin JWT |
| **Rate limit** | None |

No request body.

**Response 200** — array of alert objects for the specified user.

**Error responses**

| Code | Condition |
|------|-----------|
| 401 | Missing or invalid token |
| 403 | Caller is not ADMIN |
| 404 | User not found |

---

### POST /admin/users/\<user_id\>/alerts — Create an alert for any user *(Admin)*

| | |
|---|---|
| **Auth** | Admin JWT |
| **Rate limit** | None |

Same request body as `POST /alerts`.

**Response 201** — new alert object.

**Error responses**

| Code | Condition |
|------|-----------|
| 400 | Missing/invalid fields |
| 401 | Missing or invalid token |
| 403 | Caller is not ADMIN |
| 404 | User not found |

---

### DELETE /admin/users/\<user_id\>/alerts/\<alert_id\> — Delete a user's alert *(Admin)*

| | |
|---|---|
| **Auth** | Admin JWT |
| **Rate limit** | None |

No request body.

**Response 200**

```json
{ "message": "Alert deleted" }
```

**Error responses**

| Code | Condition |
|------|-----------|
| 401 | Missing or invalid token |
| 403 | Caller is not ADMIN |
| 404 | User or alert not found, or alert does not belong to that user |

---

### GET /admin/reports/volume — Transaction volume report *(Admin)*

| | |
|---|---|
| **Auth** | Admin JWT |
| **Rate limit** | None |

**Query parameters** (all optional): `from`, `to` — ISO 8601 date strings.

**Response 200**

```json
{
  "report": "volume",
  "filters": { "from": null, "to": null },
  "total_transactions": 500,
  "usd_to_lbp": { "count": 320, "usd_volume": 32000.0, "lbp_volume": 2864000000.0 },
  "lbp_to_usd": { "count": 180, "usd_volume": 18000.0, "lbp_volume": 1611000000.0 },
  "totals":     { "usd_volume": 50000.0, "lbp_volume": 4475000000.0 }
}
```

**Error responses**

| Code | Condition |
|------|-----------|
| 400 | Invalid date format; `from` > `to` |
| 401 | Missing or invalid token |
| 403 | Caller is not ADMIN |

---

### GET /admin/reports/activity — Most active users report *(Admin)*

| | |
|---|---|
| **Auth** | Admin JWT |
| **Rate limit** | None |

**Query parameters** (all optional)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `from` | — | ISO 8601 start date |
| `to` | — | ISO 8601 end date |
| `limit` | `10` | Top-N users to return (max 100) |

**Response 200**

```json
{
  "report": "activity",
  "filters": { "from": null, "to": null, "limit": 10 },
  "total_active_users": 3,
  "users": [
    { "user_id": 1, "user_name": "alice", "transaction_count": 50, "offer_count": 10, "total_activity": 60 },
    { "user_id": 2, "user_name": "bob",   "transaction_count": 30, "offer_count":  5, "total_activity": 35 }
  ]
}
```

**Error responses**

| Code | Condition |
|------|-----------|
| 400 | Invalid date format; `from` > `to` |
| 401 | Missing or invalid token |
| 403 | Caller is not ADMIN |

---

### GET /admin/reports/market — Marketplace statistics report *(Admin)*

| | |
|---|---|
| **Auth** | Admin JWT |
| **Rate limit** | None |

**Query parameters** (all optional): `from`, `to` — ISO 8601 date strings.

**Response 200**

```json
{
  "report": "market",
  "filters": { "from": null, "to": null },
  "total_offers": 80,
  "by_status": { "OPEN": 20, "ACCEPTED": 50, "CANCELED": 10 },
  "by_currency": { "USD_to_LBP": 55, "LBP_to_USD": 25 },
  "acceptance_rate_pct": 62.5
}
```

**Error responses**

| Code | Condition |
|------|-----------|
| 400 | Invalid date format; `from` > `to` |
| 401 | Missing or invalid token |
| 403 | Caller is not ADMIN |

---

### POST /admin/backup — Create a full database backup *(Admin)*

| | |
|---|---|
| **Auth** | Admin JWT |
| **Rate limit** | None |

No request body. Serializes users, transactions, offers, alerts, user_preferences, and wallets to a timestamped JSON file in the `backups/` directory.

**Response 200**

```json
{
  "message": "Backup created successfully",
  "filename": "backup_20260222_110500_123456.json",
  "size_bytes": 45231,
  "created_at": "2026-02-22T11:05:00.123456",
  "record_counts": {
    "users": 10, "transactions": 500, "offers": 80,
    "alerts": 25, "user_preferences": 10, "wallets": 10
  }
}
```

**Error responses**

| Code | Condition |
|------|-----------|
| 401 | Missing or invalid token |
| 403 | Caller is not ADMIN |

---

### GET /admin/backup/status — Backup status *(Admin)*

| | |
|---|---|
| **Auth** | Admin JWT |
| **Rate limit** | None |

No request body.

**Response 200 (backups exist)**

```json
{
  "has_backup": true,
  "latest_backup": {
    "filename": "backup_20260222_110500_123456.json",
    "size_bytes": 45231,
    "created_at": "2026-02-22T11:05:00.123456",
    "backup_version": "1.0",
    "record_counts": { "users": 10, "transactions": 500, ... }
  },
  "total_backups": 3,
  "all_backups": ["backup_20260222_...", "backup_20260221_...", "backup_20260220_..."],
  "backup_dir": "/path/to/backups"
}
```

**Response 200 (no backups yet)**

```json
{ "has_backup": false, "message": "No backups found. Run POST /admin/backup to create one." }
```

**Error responses**

| Code | Condition |
|------|-----------|
| 401 | Missing or invalid token |
| 403 | Caller is not ADMIN |

---

### POST /admin/restore — Restore database from a backup *(Admin)*

| | |
|---|---|
| **Auth** | Admin JWT |
| **Rate limit** | None |

**⚠ Destructive:** clears the six backed-up tables before inserting backup rows. Wrapped in a single transaction — failure triggers full rollback.

**Request body** (optional)

```json
{ "filename": "backup_20260222_110500_123456.json" }
```

If `filename` is omitted the most recent backup is used.

**Response 200**

```json
{
  "message": "Restore completed successfully",
  "filename": "backup_20260222_110500_123456.json",
  "restored_counts": {
    "users": 10, "transactions": 500, "offers": 80,
    "alerts": 25, "user_preferences": 10, "wallets": 10
  }
}
```

**Error responses**

| Code | Condition |
|------|-----------|
| 400 | Invalid filename; malformed backup JSON; missing required table keys |
| 401 | Missing or invalid token |
| 403 | Caller is not ADMIN |
| 404 | Specified backup file not found; no backups exist |
| 500 | Restore transaction failed (rolled back) |

---

## Error Response Schema

All errors return a consistent JSON body:

```json
{
  "error": "Bad Request",
  "message": "usd_amount must be a positive number",
  "status": 400
}
```

| Code | Phrase | Typical cause |
|------|--------|---------------|
| `400` | Bad Request | Missing or invalid request fields |
| `401` | Unauthorized | Missing, expired, or invalid JWT |
| `403` | Forbidden | Valid token but insufficient permissions (or wrong password on login) |
| `404` | Not Found | Resource does not exist |
| `409` | Conflict | Duplicate resource (username taken, duplicate watchlist item) |
| `429` | Too Many Requests | Rate limit exceeded (global: 60/min; login & transactions: 5/min) |
| `500` | Internal Server Error | Unexpected server-side failure |
