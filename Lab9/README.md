# Currency Exchange — Android App (Sprint 4 / Lab 9)

A Material Design Android app for USD/LBP currency exchange. Connects to a Flask REST backend via Retrofit.

---

## Setup — Running in Android Studio

1. **Open the project**
   - Launch Android Studio → `File → Open` → select the `Lab9/` folder.

2. **Configure the backend URL** *(see section below)*

3. **Run the backend**
   - From the `Majd Ayash- sprint4/` root, run:
     ```
     python -m flask --app sprint1_backend.app run --debug
     ```
   - The server starts at `http://127.0.0.1:5000`.

4. **Run the app**
   - Select an emulator or physical device from the toolbar and press **Run ▶**.
   - The app requires an active network connection to the backend.

---

## Configuring the Backend URL

Open:
```
app/src/main/kotlin/com/example/currencyexchange/api/retrofit.kt
```

Change the `BASE_URL` constant at the top of the file:

```kotlin
private const val BASE_URL = "http://10.0.2.2:5000/"
```

| Target device | URL to use |
|---------------|------------|
| Android Emulator | `http://10.0.2.2:5000/` |
| Physical device (USB/Wi-Fi) | `http://<your-machine-LAN-IP>:5000/` e.g. `http://192.168.1.10:5000/` |

> **Why 10.0.2.2?** The Android emulator runs inside a virtual machine. `10.0.2.2` is a special alias that the emulator maps to the host machine's `localhost`. A physical device is on your real LAN, so it needs your machine's actual IP address (find it with `ipconfig` on Windows or `ifconfig` on macOS/Linux).

---

## Requirements

| Requirement | Value |
|-------------|-------|
| Minimum SDK | API 21 (Android 5.0 Lollipop) |
| Target SDK | API 34 (Android 14) |
| Compile SDK | API 34 |
| Language | Kotlin |
| Backend | Python 3.9+ / Flask / MySQL 8.0+ |

---

## Project Structure

```
Lab9/
└── app/src/main/
    ├── kotlin/com/example/currencyexchange/
    │   ├── MainActivity.kt          — tabs, FAB, auth UI
    │   ├── LoginActivity.kt         — login form
    │   ├── RegistrationActivity.kt  — registration form
    │   ├── ExchangeFragment.kt      — rates display + calculator
    │   ├── TransactionsFragment.kt  — transaction history list
    │   ├── ProofPanelManager.kt     — live header bar (user/screen/clock)
    │   ├── SessionManager.kt        — handleSessionExpired()
    │   ├── TabsPagerAdapter.kt      — ViewPager2 tab adapter
    │   └── api/
    │       ├── retrofit.kt          — Retrofit setup + BASE_URL
    │       ├── Authentication.kt    — token + username SharedPreferences
    │       └── model/               — data classes (Transaction, User, etc.)
    └── res/layout/
        ├── activity_main.xml
        ├── activity_login.xml
        ├── activity_registration.xml
        ├── fragment_exchange.xml
        ├── fragment_transactions.xml
        ├── layout_proof_panel.xml
        ├── item_transaction.xml
        ├── dialog_transaction.xml
        └── dialog_wallet.xml
```

---

## Implemented Features

### Authentication
- User registration with auto-login on success
- User login with JWT token stored in `SharedPreferences`
- Username persisted alongside token for display
- Logout clears token and username
- Session expiry handling (`handleSessionExpired`) — clears credentials, navigates to Login, clears back stack

### Proof Panel
- Persistent dark header bar on every screen
- Shows: logged-in username (or "Guest"), current screen name, live clock updating every second via `Handler`

### Exchange Rates (Exchange tab)
- Fetches live USD/LBP rates from the backend (`GET /exchangeRate`)
- ProgressBar shown during fetch
- Error state with message and Retry button on failure
- 429 rate-limit handling: disables Refresh button for 30 seconds
- Refresh Rates button to manually re-fetch

### Exchange Calculator
- Convert USD → LBP or LBP → USD using fetched rates
- Input validation: empty check, numeric check, positive-value check — errors shown via `setError()` on the field
- Formatted output: `$ 1,234.56` / `L.L. 89,500`
- Shows "Rates not available yet. Please wait." if rates haven't loaded

### Transaction History (Transactions tab)
- Fetches user's transactions (`GET /transaction`) with Bearer token
- ProgressBar during fetch
- "Please log in to view transactions" shown when logged out
- "No transactions found" shown when list is empty
- Card-based list showing: colored direction label (BUY USD green / SELL USD red), USD amount, LBP amount, formatted date
- Re-fetches on every tab resume and after login/logout
- 401 triggers `handleSessionExpired`

### Add Transaction (FAB)
- Dialog with USD amount, LBP amount, and Buy/Sell direction
- Full validation before API call: empty, non-numeric, non-positive, no direction selected
- HTTP error handling: 400 → invalid data, 401 → session expired, 403 → permission denied, 429 → disables FAB for 30 seconds
- Dialog stays open on validation or server errors; closes only on success

### Fund Wallet
- Dialog to set USD and LBP balances (`PUT /wallet`)
- Visible only when logged in

### Error Handling (all screens)
- 401 on protected endpoints → `handleSessionExpired` → clears session, Snackbar, navigates to Login
- 403 → "Access forbidden" or context-specific message
- 429 → disables the triggering button/FAB for 30 seconds
- Network failure → descriptive Snackbar message

---

## Remaining Known Inconsistencies

See code review notes below.
