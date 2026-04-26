# Currency Exchange — Sprint 4

**Author:** Majd Ayash

A full-stack USD/LBP currency exchange platform consisting of a Flask REST backend and two iterations of an Android client built across two labs.

---

## Repository Structure

```
Majd Ayash- sprint4/
├── sprint1_backend/     # Python/Flask REST API
├── Lab8/                # Android app — base implementation
└── Lab9/                # Android app — full-featured implementation (Sprint 4)
```

---

## 1. sprint1_backend — Flask REST API

A RESTful backend for the currency exchange platform. Handles user authentication, exchange rate tracking, transaction recording, wallet management, and more.

### Tech Stack
- Python 3.9+
- Flask + SQLAlchemy
- MySQL 8.0+
- JWT authentication (PyJWT)

### Setup & Run

1. **Install dependencies**
   ```bash
   pip install -r sprint1_backend/requirements.txt
   ```

2. **Configure the database**

   Open `sprint1_backend/db_config.py` and set your MySQL credentials:
   ```python
   DB_CONFIG = "mysql+pymysql://<user>:<password>@127.0.0.1:3306/exchange"
   ```

   Create the database in MySQL:
   ```sql
   CREATE DATABASE exchange CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   ```

3. **Run the server**
   ```bash
   python -m flask --app sprint1_backend.app run --debug
   ```

   Server starts at `http://127.0.0.1:5000`. Tables are created automatically on first startup.

### Key Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/user` | Register a new user |
| POST | `/authentication` | Login — returns JWT token |
| GET | `/exchangeRate` | Current buy/sell rates |
| POST | `/transaction` | Submit a transaction |
| GET | `/transaction` | List user's transactions |
| PUT | `/wallet` | Update wallet balances |

---

## 2. Lab8 — Android App (Base Implementation)

The initial Android client built in Lab 8. Establishes the foundation: single-screen architecture, Retrofit API integration, basic authentication dialogs, and transaction submission.

### Features
- Single `MainActivity` with login/register dialogs
- Exchange rate display fetched from the backend
- Add transaction dialog (USD amount, LBP amount, direction)
- Fund Wallet dialog
- JWT token stored and attached to protected requests
- Retrofit 2 + Gson for all API calls

### Tech Stack
- Kotlin
- Material Design Components
- Retrofit 2 / Gson
- Minimum SDK: API 21

### Setup
1. Open `Lab8/Lab_8/` in Android Studio
2. Set the backend URL in `app/src/main/kotlin/com/example/currencyexchange/api/retrofit.kt`:
   ```kotlin
   private const val BASE_URL = "http://10.0.2.2:5000/"  // emulator
   // or your machine's LAN IP for a physical device
   ```
3. Run the backend, then press Run ▶ in Android Studio

---

## 3. Lab9 — Android App (Sprint 4 — Full Implementation)

The complete Sprint 4 Android client, built on top of Lab 8. Adds multi-screen navigation, a tabbed interface, full error handling, input validation, session management, and a live proof panel.

### Features

**Authentication**
- Login and Registration as dedicated Activities
- JWT token and username persisted in `SharedPreferences`
- Logout clears all credentials
- `handleSessionExpired()` — clears session, navigates to Login, clears back stack

**Proof Panel**
- Persistent dark header bar on every screen
- Shows logged-in username (or "Guest"), screen name, and a live clock (updates every second)

**Exchange Tab**
- Live USD/LBP rate display with ProgressBar during fetch
- Error state with Retry button
- Exchange calculator with input validation and formatted output
- 429 handling — Refresh button disabled for 30 seconds

**Transactions Tab**
- Card-based transaction list (color-coded direction, formatted amounts and dates)
- ProgressBar during fetch
- "Please log in" / "No transactions found" empty states
- Re-fetches on every resume and after login/logout
- 401 → session expiry handling

**Add Transaction (FAB)**
- Full input validation with `setError()` on fields
- HTTP error handling: 400, 401, 403, 429
- Dialog stays open on error; closes only on success

**Fund Wallet**
- Set USD and LBP balances via dialog

### Tech Stack
- Kotlin
- Material Design Components (OutlinedBox inputs, MaterialButton, CardView, FAB)
- Retrofit 2 / Gson
- ViewPager2 + TabLayout
- Handler-based live clock and rate-limit timers
- Minimum SDK: API 21

### Setup
1. Open `Lab9/` in Android Studio
2. Set the backend URL in `Lab9/app/src/main/kotlin/com/example/currencyexchange/api/retrofit.kt`:
   ```kotlin
   private const val BASE_URL = "http://10.0.2.2:5000/"  // emulator
   // use your machine's LAN IP for a physical device, e.g. http://192.168.1.10:5000/
   ```
3. Run the backend (`sprint1_backend`), then press Run ▶ in Android Studio

> **Note:** `10.0.2.2` is the special alias the Android emulator uses to reach the host machine's localhost. For a physical device connected over Wi-Fi, replace it with your machine's local IP address (find it with `ipconfig` on Windows).

---

## Running Everything Together

1. Start MySQL
2. Run the backend:
   ```bash
   python -m flask --app sprint1_backend.app run --debug
   ```
3. Open `Lab9/` in Android Studio and run the app on an emulator or device
4. The app connects to `http://10.0.2.2:5000` by default (emulator)

---

## Requirements Summary

| Component | Requirement |
|-----------|-------------|
| Python | 3.9+ |
| MySQL | 8.0+ |
| Android Studio | Hedgehog or newer |
| Minimum Android SDK | API 21 (Android 5.0) |
| Target Android SDK | API 34 (Android 14) |
