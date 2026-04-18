# API Documentation — USD/LBP Currency Exchange Backend

---

## General Rules

- All requests and responses use JSON (except the CSV export endpoint).
- To access a protected endpoint, include this header:
  - Authorization: Bearer YOUR_TOKEN_HERE
- Get a token by calling POST /authentication.
- All error responses follow this format:
  - "error": short error title
  - "message": detailed description
  - "status": HTTP status code

---

## 1. Register a New User

- Route: POST /user
- Authentication required: No
- Rate limit: None

Request body fields:
- user_name (text, required) — must be unique and not empty
- password (text, required) — plain text, will be stored securely
- role (text, optional) — either "USER" or "ADMIN", defaults to "USER"

Example request:
- user_name: "alice"
- password: "secret123"
- role: "USER"

Example success response (status 201):
- id: 1
- user_name: "alice"
- role: "USER"
- status: "ACTIVE"
- created_at: "2026-02-22T10:00:00"

Possible errors:
- 400 — missing user_name or password, empty string, or invalid role value
- 409 — username is already taken

---

## 2. Log In and Get a Token

- Route: POST /authentication
- Authentication required: No
- Rate limit: 5 requests per minute

Request body fields:
- user_name (text, required)
- password (text, required)

Example request:
- user_name: "alice"
- password: "secret123"

Example success response (status 200):
- token: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
- user: object containing id, user_name, role, status, created_at

Possible errors:
- 400 — missing user_name or password
- 401 — account is banned
- 403 — wrong password or unknown username
- 429 — too many login attempts

---

## 3. Submit a Currency Exchange Transaction

- Route: POST /transaction
- Authentication required: Yes
- Rate limit: 5 requests per minute

Request body fields:
- usd_amount (number, required) — must be greater than 0
- lbp_amount (number, required) — must be greater than 0
- transaction_type (text, required) — either "usd-to-lbp" or "lbp-to-usd"

Example request:
- usd_amount: 100
- lbp_amount: 89500
- transaction_type: "usd-to-lbp"

Example success response (status 201):
- ok: true
- transaction:
  - id: 42
  - usd_amount: 100.0
  - lbp_amount: 89500.0
  - usd_to_lbp: true
  - user_id: 1
  - added_date: "2026-02-22T10:05:00"

Possible errors:
- 400 — missing or invalid amounts or direction; rate is more than 20% away from the recent average (outlier detected); not enough wallet balance
- 401 — missing or invalid token
- 429 — too many requests

---

## 4. List Your Transactions

- Route: GET /transaction
- Authentication required: Yes
- Rate limit: None

No request body needed. No filters.

Example success response (status 200):
- Returns a list of transaction objects, each containing:
  - id, usd_amount, lbp_amount, usd_to_lbp, user_id, added_date

Possible errors:
- 401 — missing or invalid token

---

## 5. Export Transactions as a CSV File

- Route: GET /transactions/export
- Authentication required: Yes
- Rate limit: None

Optional query parameters:
- from — start date in ISO format (example: 2026-01-01)
- to — end date in ISO format (example: 2026-02-01)

The response is a downloadable CSV file with these columns:
- ID, USD Amount, LBP Amount, Direction, Date, Exchange Rate

Possible errors:
- 400 — invalid date format in "from" or "to"
- 401 — missing or invalid token

---

## 6. Get Current Exchange Rates

- Route: GET /exchangeRate
- Authentication required: No
- Rate limit: None

No request body needed. Calculates rates from all transactions in the last 72 hours.

Example success response (status 200):
- usd_to_lbp: 89500.0 (or null if no data)
- lbp_to_usd: 89000.0 (or null if no data)
- buy_usd: 89000.0
- sell_usd: 89500.0

Note: buy_usd and sell_usd are aliases for lbp_to_usd and usd_to_lbp.

Possible errors:
- None — always returns 200; missing data shows as null

---

## 7. Get Historical Exchange Rate Data

- Route: GET /history/rate
- Authentication required: Yes
- Rate limit: None

Optional query parameters (falls back to saved user preferences if not provided):
- from — ISO datetime for start of range
- to — ISO datetime for end of range
- interval — either "hour" or "day"

Example success response (status 200):
- Returns a list of time buckets, each containing:
  - timestamp: "2026-02-22T10:00:00"
  - avg_rate: 89500.0
  - min_rate: 89200.0
  - max_rate: 89800.0
  - count: 5

Possible errors:
- 400 — invalid date format, invalid interval value, or "from" is not before "to"
- 401 — missing or invalid token
- 404 — no transactions found in the given date range

---

## 8. Get Exchange Rate Analytics

- Route: GET /analytics/rate
- Authentication required: Yes
- Rate limit: None

Optional query parameters (falls back to saved user preferences if not provided):
- from — ISO datetime for start of range
- to — ISO datetime for end of range
- direction — either "USD_LBP" or "LBP_USD"

Example success response (status 200):
- min: 88000.0
- max: 91000.0
- avg: 89500.0
- count: 12
- percentage_change: 1.5
- volatility: 300.5
- trend: "up" (can be "up", "down", or "flat")

Possible errors:
- 400 — invalid date or direction, or "from" is not before "to"
- 401 — missing or invalid token
- 404 — no transactions found for that direction and range

---

## 9. Post a P2P Exchange Offer

- Route: POST /market/offers
- Authentication required: Yes
- Rate limit: None

Request body fields:
- from_currency (text, required) — "USD" or "LBP"
- to_currency (text, required) — "USD" or "LBP", must be different from from_currency
- amount_from (number, required) — amount being offered, must be greater than 0
- rate (number, required) — LBP per USD, must be greater than 0

Example request:
- from_currency: "USD"
- to_currency: "LBP"
- amount_from: 100
- rate: 89500

Example success response (status 201):
- id: 7
- creator_user_id: 1
- from_currency: "USD"
- to_currency: "LBP"
- amount_from: 100.0
- rate: 89500.0
- status: "OPEN"
- created_at: "2026-02-22T11:00:00"
- updated_at: null

Possible errors:
- 400 — missing field, same currency for both sides, non-positive amount or rate
- 401 — missing or invalid token

---

## 10. Browse Open Offers

- Route: GET /market/offers
- Authentication required: Yes
- Rate limit: None

Optional query parameters:
- from_currency — filter by "USD" or "LBP"
- to_currency — filter by "USD" or "LBP"

Example success response (status 200):
- Returns a list of open offer objects (same structure as the POST /market/offers response)

Possible errors:
- 400 — invalid currency value in filter
- 401 — missing or invalid token

---

## 11. Accept an Offer

- Route: POST /market/offers/{offer_id}/accept
- Authentication required: Yes
- Rate limit: 5 requests per minute

No request body needed.

What happens on success:
- The offer status becomes "ACCEPTED"
- A trade record is created
- Wallet balances are transferred between buyer and seller

Example success response (status 200):
- All offer fields plus:
- trade_id: 3

Possible errors:
- 400 — offer is not open; you are trying to accept your own offer; insufficient wallet balance for buyer or seller
- 401 — missing or invalid token
- 404 — offer not found
- 429 — too many requests

---

## 12. Cancel an Offer

- Route: POST /market/offers/{offer_id}/cancel
- Authentication required: Yes
- Rate limit: None

No request body needed.

Example success response (status 200):
- Returns the updated offer object with status "CANCELED"

Possible errors:
- 400 — offer is not in "OPEN" status
- 401 — missing or invalid token
- 403 — you are not the creator of this offer
- 404 — offer not found

---

## 13. View Your Own Offers

- Route: GET /market/me/offers
- Authentication required: Yes
- Rate limit: None

No request body needed. Returns all your offers in all statuses, newest first.

Example success response (status 200):
- Returns a list of offer objects

Possible errors:
- 401 — missing or invalid token

---

## 14. View Your Completed Trades

- Route: GET /market/me/trades
- Authentication required: Yes
- Rate limit: None

No request body needed. Returns all trades where you were either the buyer or seller, newest first.

Example success response (status 200):
- Returns a list of trade objects, each containing:
  - id, offer_id, buyer_user_id, seller_user_id, from_currency, to_currency, amount_from, rate, executed_at

Possible errors:
- 401 — missing or invalid token

---

## 15. Create a Price Alert

- Route: POST /alerts
- Authentication required: Yes
- Rate limit: None

Request body fields:
- direction (text, required) — "USD_LBP" or "LBP_USD"
- threshold (number, required) — must be greater than 0
- condition (text, required) — "ABOVE" or "BELOW"

Example request:
- direction: "USD_LBP"
- threshold: 90000
- condition: "ABOVE"

Example success response (status 201):
- id: 5
- user_id: 1
- direction: "USD_LBP"
- threshold: 90000.0
- condition: "ABOVE"
- triggered: false
- triggered_at: null
- created_at: "2026-02-22T12:00:00"

Possible errors:
- 400 — invalid direction or condition; missing or non-positive threshold
- 401 — missing or invalid token

---

## 16. List Your Alerts

- Route: GET /alerts
- Authentication required: Yes
- Rate limit: None

No request body needed. Returns your alerts newest first.

Example success response (status 200):
- Returns a list of alert objects (same structure as the POST /alerts response)

Possible errors:
- 401 — missing or invalid token

---

## 17. Delete an Alert

- Route: DELETE /alerts/{alert_id}
- Authentication required: Yes
- Rate limit: None

No request body needed.

Example success response (status 200):
- message: "Alert deleted successfully"

Possible errors:
- 401 — missing or invalid token
- 403 — this alert belongs to another user
- 404 — alert not found

---

## 18. List Your Notifications

- Route: GET /notifications
- Authentication required: Yes
- Rate limit: None

Optional query parameters:
- unread — set to "true" to return only unread notifications (default: false)
- limit — maximum number to return, up to 200 (default: 50)
- offset — how many to skip for pagination (default: 0)

Example success response (status 200):
- Returns a list of notification objects, each containing:
  - id, user_id, type, message, metadata, read_at, created_at

Possible errors:
- 401 — missing or invalid token

---

## 19. Mark a Notification as Read

- Route: PATCH /notifications/{notification_id}/read
- Authentication required: Yes
- Rate limit: None

No request body needed. Sets the read_at timestamp to now.

Example success response (status 200):
- Returns the updated notification object

Possible errors:
- 401 — missing or invalid token
- 403 — this notification belongs to another user
- 404 — notification not found

---

## 20. Delete a Notification

- Route: DELETE /notifications/{notification_id}
- Authentication required: Yes
- Rate limit: None

No request body needed.

Example success response (status 200):
- message: "Notification deleted successfully"

Possible errors:
- 401 — missing or invalid token
- 403 — this notification belongs to another user
- 404 — notification not found

---

## 21. Add an Item to Your Watchlist

- Route: POST /watchlist
- Authentication required: Yes
- Rate limit: None

Request body fields:
- type (text, required) — label for the item, e.g. "rate_threshold"
- payload_json (object or JSON string, required) — custom payload; used for duplicate detection

Example request:
- type: "rate_threshold"
- payload_json: { "direction": "USD_LBP", "threshold": 90000 }

Example success response (status 201):
- id: 3
- user_id: 1
- type: "rate_threshold"
- payload_json: '{"direction": "USD_LBP", "threshold": 90000}'
- created_at: "2026-02-22T13:00:00"

Possible errors:
- 400 — missing type or payload_json; payload_json is not valid JSON
- 401 — missing or invalid token
- 409 — you already have an identical watchlist item

---

## 22. List Your Watchlist

- Route: GET /watchlist
- Authentication required: Yes
- Rate limit: None

No request body needed. Returns your items newest first.

Example success response (status 200):
- Returns a list of watchlist item objects

Possible errors:
- 401 — missing or invalid token

---

## 23. Remove a Watchlist Item

- Route: DELETE /watchlist/{item_id}
- Authentication required: Yes
- Rate limit: None

No request body needed.

Example success response (status 200):
- message: "Watchlist item deleted successfully"

Possible errors:
- 401 — missing or invalid token
- 403 — this item belongs to another user
- 404 — item not found

---

## 24. Get Your Analytics Preferences

- Route: GET /preferences
- Authentication required: Yes
- Rate limit: None

No request body needed. Creates default preferences if you have none yet.

Example success response (status 200):
- user_id: 1
- default_from_range_hours: 24
- default_interval: "hour"
- default_direction: "USD_LBP"
- updated_at: null

Possible errors:
- 401 — missing or invalid token

---

## 25. Update Your Analytics Preferences

- Route: PUT /preferences
- Authentication required: Yes
- Rate limit: None

Request body fields (all optional — only the fields you include will be updated):
- default_from_range_hours (integer) — must be between 1 and 8760
- default_interval (text) — "hour" or "day"
- default_direction (text) — "USD_LBP" or "LBP_USD"

Example request:
- default_from_range_hours: 72
- default_interval: "day"
- default_direction: "LBP_USD"

Example success response (status 200):
- Returns the updated preferences object

Possible errors:
- 400 — invalid value for any field
- 401 — missing or invalid token

---

## 26. Get Your Wallet Balances

- Route: GET /wallet
- Authentication required: Yes
- Rate limit: None

No request body needed. Creates a zero-balance wallet if you have none yet.

Example success response (status 200):
- user_id: 1
- usd_balance: 500.0
- lbp_balance: 44750000.0
- created_at: "2026-02-20T09:00:00"
- updated_at: "2026-02-22T11:05:00"

Possible errors:
- 401 — missing or invalid token

---

## 27. Set Your Wallet Balances

- Route: PUT /wallet
- Authentication required: Yes
- Rate limit: None

Request body fields (all optional):
- usd_balance (number) — cannot be negative
- lbp_balance (number) — cannot be negative

Example request:
- usd_balance: 500.0
- lbp_balance: 1000000.0

Example success response (status 200):
- Returns the updated wallet object

Possible errors:
- 400 — non-numeric value or negative balance
- 401 — missing or invalid token

---

## 28. Get a Wallet by User ID

- Route: GET /wallet/user/{user_id}
- Authentication required: Yes
- Rate limit: None

No request body needed. Creates a zero-balance wallet if the user has none yet.

Example success response (status 200):
- Returns the wallet object for that user

Possible errors:
- 401 — missing or invalid token

---

## 29. View Your Audit Log

- Route: GET /me/audit
- Authentication required: Yes
- Rate limit: None

Optional query parameters:
- limit — max records to return, up to 500 (default: 100)
- offset — pagination offset (default: 0)
- event_type — filter by type, e.g. "login_attempt" or "transaction_submitted"

Example success response (status 200):
- Returns a list of audit log entries, each containing:
  - id, user_id, event_type, success, metadata, created_at

Possible errors:
- 401 — missing or invalid token

---

## 30. List All Users (Admin Only)

- Route: GET /admin/users
- Authentication required: Yes, Admin role
- Rate limit: None

No request body needed.

Example success response (status 200):
- Returns a list of all users, each with: id, user_name, role, status, created_at

Possible errors:
- 401 — missing or invalid token
- 403 — you are not an admin

---

## 31. Change a User's Account Status (Admin Only)

- Route: PATCH /admin/users/{user_id}/status
- Authentication required: Yes, Admin role
- Rate limit: None

Request body fields:
- status (text, required) — "ACTIVE", "SUSPENDED", or "BANNED"

Example request:
- status: "BANNED"

Example success response (status 200):
- Returns the updated user summary

Possible errors:
- 400 — missing status or invalid value
- 401 — missing or invalid token
- 403 — you are not an admin
- 404 — user not found

---

## 32. View Platform-Wide Transaction Statistics (Admin Only)

- Route: GET /admin/stats/transactions
- Authentication required: Yes, Admin role
- Rate limit: None

No request body needed.

Example success response (status 200):
- total_transactions: 500
- usd_to_lbp_count: 320
- lbp_to_usd_count: 180
- usd_to_lbp_volume_usd: 32000.0
- lbp_to_usd_volume_usd: 18000.0
- unique_users: 45
- earliest_transaction: "2026-01-01T08:00:00"
- latest_transaction: "2026-02-22T11:05:00"

Possible errors:
- 401 — missing or invalid token
- 403 — you are not an admin

---

## 33. View All Audit Logs (Admin Only)

- Route: GET /admin/audit
- Authentication required: Yes, Admin role
- Rate limit: None

Optional query parameters:
- limit — max records, up to 1000 (default: 100)
- offset — pagination offset (default: 0)
- event_type — filter by event type
- user_id — filter by a specific user's ID
- success — "true" or "false"

Example success response (status 200):
- Returns a list of audit log entries (same structure as GET /me/audit)

Possible errors:
- 401 — missing or invalid token
- 403 — you are not an admin

---

## 34. View Rate Quality Dashboard (Admin Only)

- Route: GET /admin/rate/quality
- Authentication required: Yes, Admin role
- Rate limit: None

Optional query parameters:
- limit — number of recent anomalies to return, up to 100 (default: 20)

Example success response (status 200):
- sources_summary: list of rate sources with count and average rate
- anomalies:
  - recent: list of recent flagged outlier rates
  - total_count: all-time anomaly count
  - last_24h_count: anomalies in the last 24 hours
- thresholds:
  - percent_change: 20 (the deviation threshold used)
  - time_window_minutes: 180

Possible errors:
- 401 — missing or invalid token
- 403 — you are not an admin

---

## 35. Get a User's Preferences (Admin Only)

- Route: GET /admin/users/{user_id}/preferences
- Authentication required: Yes, Admin role
- Rate limit: None

No request body needed. Creates defaults if the user has none.

Example success response (status 200):
- Returns the preference object for that user

Possible errors:
- 401 — missing or invalid token
- 403 — you are not an admin
- 404 — user not found

---

## 36. Update a User's Preferences (Admin Only)

- Route: PUT /admin/users/{user_id}/preferences
- Authentication required: Yes, Admin role
- Rate limit: None

Same request body as PUT /preferences.

Example success response (status 200):
- Returns the updated preferences object

Possible errors:
- 400 — invalid field value
- 401 — missing or invalid token
- 403 — you are not an admin
- 404 — user not found

---

## 37. List a User's Alerts (Admin Only)

- Route: GET /admin/users/{user_id}/alerts
- Authentication required: Yes, Admin role
- Rate limit: None

No request body needed.

Example success response (status 200):
- Returns a list of alert objects for that user

Possible errors:
- 401 — missing or invalid token
- 403 — you are not an admin
- 404 — user not found

---

## 38. Create an Alert for a User (Admin Only)

- Route: POST /admin/users/{user_id}/alerts
- Authentication required: Yes, Admin role
- Rate limit: None

Same request body as POST /alerts.

Example success response (status 201):
- Returns the new alert object

Possible errors:
- 400 — missing or invalid fields
- 401 — missing or invalid token
- 403 — you are not an admin
- 404 — user not found

---

## 39. Delete a User's Alert (Admin Only)

- Route: DELETE /admin/users/{user_id}/alerts/{alert_id}
- Authentication required: Yes, Admin role
- Rate limit: None

No request body needed.

Example success response (status 200):
- message: "Alert deleted"

Possible errors:
- 401 — missing or invalid token
- 403 — you are not an admin
- 404 — user or alert not found, or the alert does not belong to that user

---

## 40. Transaction Volume Report (Admin Only)

- Route: GET /admin/reports/volume
- Authentication required: Yes, Admin role
- Rate limit: None

Optional query parameters:
- from — ISO date for start of range
- to — ISO date for end of range

Example success response (status 200):
- report: "volume"
- filters: the from/to dates used
- total_transactions: 500
- usd_to_lbp: count, usd_volume, lbp_volume
- lbp_to_usd: count, usd_volume, lbp_volume
- totals: combined usd_volume and lbp_volume

Possible errors:
- 400 — invalid date format, or "from" is after "to"
- 401 — missing or invalid token
- 403 — you are not an admin

---

## 41. Most Active Users Report (Admin Only)

- Route: GET /admin/reports/activity
- Authentication required: Yes, Admin role
- Rate limit: None

Optional query parameters:
- from — ISO date for start of range
- to — ISO date for end of range
- limit — how many top users to return, up to 100 (default: 10)

Example success response (status 200):
- report: "activity"
- filters: from, to, limit used
- total_active_users: 3
- users: list of users ranked by activity, each with:
  - user_id, user_name, transaction_count, offer_count, total_activity

Possible errors:
- 400 — invalid date format, or "from" is after "to"
- 401 — missing or invalid token
- 403 — you are not an admin

---

## 42. Marketplace Statistics Report (Admin Only)

- Route: GET /admin/reports/market
- Authentication required: Yes, Admin role
- Rate limit: None

Optional query parameters:
- from — ISO date for start of range
- to — ISO date for end of range

Example success response (status 200):
- report: "market"
- filters: from and to used
- total_offers: 80
- by_status: OPEN count, ACCEPTED count, CANCELED count
- by_currency: USD_to_LBP count, LBP_to_USD count
- acceptance_rate_pct: 62.5

Possible errors:
- 400 — invalid date format, or "from" is after "to"
- 401 — missing or invalid token
- 403 — you are not an admin

---

## 43. Create a Database Backup (Admin Only)

- Route: POST /admin/backup
- Authentication required: Yes, Admin role
- Rate limit: None

No request body needed. Saves a JSON snapshot of all data to the backups/ folder.

Tables included in backup: users, transactions, offers, alerts, user_preferences, wallets.

Example success response (status 200):
- message: "Backup created successfully"
- filename: "backup_20260222_110500_123456.json"
- size_bytes: 45231
- created_at: "2026-02-22T11:05:00.123456"
- record_counts: per-table record totals

Possible errors:
- 401 — missing or invalid token
- 403 — you are not an admin

---

## 44. Check Backup Status (Admin Only)

- Route: GET /admin/backup/status
- Authentication required: Yes, Admin role
- Rate limit: None

No request body needed.

Example success response when a backup exists (status 200):
- has_backup: true
- latest_backup: filename, size_bytes, created_at, backup_version, record_counts
- total_backups: 3
- all_backups: list of all backup filenames
- backup_dir: path to backups folder

Example success response when no backup exists (status 200):
- has_backup: false
- message: "No backups found. Run POST /admin/backup to create one."

Possible errors:
- 401 — missing or invalid token
- 403 — you are not an admin

---

## 45. Restore Database from a Backup (Admin Only)

- Route: POST /admin/restore
- Authentication required: Yes, Admin role
- Rate limit: None

WARNING: This operation clears the existing data for all six backed-up tables before restoring.

Request body fields (optional):
- filename (text) — name of the backup file to restore from; uses the most recent backup if not provided

Example request:
- filename: "backup_20260222_110500_123456.json"

Example success response (status 200):
- message: "Restore completed successfully"
- filename: "backup_20260222_110500_123456.json"
- restored_counts: per-table record totals

Possible errors:
- 400 — invalid filename; malformed backup JSON; backup is missing required tables
- 401 — missing or invalid token
- 403 — you are not an admin
- 404 — specified backup file not found; no backups exist at all
- 500 — restore failed and was rolled back

---

## Error Code Reference

- 400 Bad Request — the request body or query parameters are missing or invalid
- 401 Unauthorized — the JWT token is missing, expired, or invalid
- 403 Forbidden — valid token but not enough permissions, or wrong password on login
- 404 Not Found — the requested resource does not exist
- 409 Conflict — duplicate resource, such as a username that is already taken
- 429 Too Many Requests — rate limit hit (global: 60 per minute; login and transactions: 5 per minute)
- 500 Internal Server Error — unexpected failure on the server side
