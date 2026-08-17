# End-to-End Test: Signup, Email Verification, Login, Session, Password Reset

## Overview

Tests the full console auth pipeline:

1. Register a new account (creates tenant, sends verification email)
2. Verify the email (local dev has no SMTP, so the token is set manually via a container script)
3. Login and receive an access token + refresh token
4. Call an authenticated endpoint (`/auth/me`)
5. Refresh the access token
6. Forgot password → reset password → confirm old sessions are invalidated
7. Resend verification (enumeration-safe) and logout

All endpoints are under `/console/api/auth/*` (see `src/controllers/console/auth.py`).

Every step below was run and verified against a live local stack on 2026-08-13.

## Prerequisites

- API running on `http://localhost:5001` (`docker compose up -d`, or already running)
- Verification/reset emails are queued via `send_verification_email_task` /
  `send_password_reset_email_task` but won't actually deliver without SMTP configured — expected in
  local dev. We bypass that below by generating the token the same way the app does.
- Postgres reachable via `docker compose exec -T postgres` (service name `postgres`, container
  `synkora-postgres`, db/user `synkora`/`synkora` — confirm with `docker compose ps` if different)

Run all commands via `docker compose exec -T api ...` from the repo root. Do **not** use local
Python — this project has no local env, only Docker (see `MEMORY.md`).

---

## Step 1 — Register a New Account

Password policy (`PasswordValidator`): min 12 chars, upper + lower + digit + special char. Registration
also runs a HaveIBeenPwned (HIBP) breach check — common test passwords like `TestPass123!@#` get
rejected with `422`. Use a less guessable one.

```python
docker compose exec -T api python3 -c "
import urllib.request, json, urllib.error

payload = json.dumps({
    'email': 'e2e-test-user@localhost.com',
    'password': 'Xk9#mQ7vLp2\$ZnR4',
    'name': 'E2E Test User',
    'tenant_name': 'E2E Test Org'
}).encode()

req = urllib.request.Request(
    'http://localhost:5001/console/api/auth/register',
    data=payload,
    headers={'Content-Type': 'application/json'},
    method='POST'
)
try:
    with urllib.request.urlopen(req) as r:
        print(r.status, r.read().decode())
except urllib.error.HTTPError as e:
    print(e.code, e.read().decode())
"
```

Verified response (`201`):

```json
{"success":true,"data":{"account":{"id":"...","email":"e2e-test-user@localhost.com","name":"E2E Test User","status":"INACTIVE"},"tenant":{"id":"...","name":"E2E Test Org","plan":"FREE","status":"ACTIVE"}},"message":"Registration successful. Please check your email to verify your account."}
```

Note `status: "INACTIVE"` — the account cannot log in until email verification completes
(`AuthService.authenticate` rejects any account where `status != ACTIVE`).

---

## Step 2 — Attempt Login Before Verification (Expect 401)

```python
docker compose exec -T api python3 -c "
import urllib.request, json, urllib.error

payload = json.dumps({'email': 'e2e-test-user@localhost.com', 'password': 'Xk9#mQ7vLp2\$ZnR4'}).encode()
req = urllib.request.Request(
    'http://localhost:5001/console/api/auth/login',
    data=payload,
    headers={'Content-Type': 'application/json'},
    method='POST'
)
try:
    with urllib.request.urlopen(req) as r:
        print(r.status, r.read().decode())
except urllib.error.HTTPError as e:
    print(e.code, e.read().decode())
"
```

Verified: `401` — `{"detail":"Invalid email or password"}` (an inactive account intentionally
returns the same generic error as a wrong password, to avoid leaking account state).

---

## Step 3 — Manually Verify the Email (No SMTP in Local Dev)

The verification token is generated in-process and only ever leaves the app inside the email body
(`AuthService.send_verification_email`). Since local dev has no SMTP/SendGrid/etc. configured, the
email silently fails to send. To unblock testing, generate and store a token the same way the app
does, then call the public verify endpoint with the raw value:

```python
docker compose exec -T api python3 -c "
import asyncio
from sqlalchemy import select
from src.core.database import get_async_session_factory
from src.models import Account
from src.services.auth_service import AuthService

async def main():
    factory = get_async_session_factory()
    async with factory() as db:
        result = await db.execute(select(Account).filter_by(email='e2e-test-user@localhost.com'))
        account = result.scalar_one()
        token = AuthService.generate_verification_token()
        account.email_verification_token = AuthService.hash_token(token)
        await db.commit()
        print('RAW_TOKEN=' + token)

asyncio.run(main())
"
```

Copy the printed `RAW_TOKEN`, then call the verify endpoint:

```python
docker compose exec -T api python3 -c "
import urllib.request, json
TOKEN = '<paste RAW_TOKEN here>'
payload = json.dumps({'token': TOKEN}).encode()
req = urllib.request.Request(
    'http://localhost:5001/console/api/auth/verify-email',
    data=payload,
    headers={'Content-Type': 'application/json'},
    method='POST'
)
with urllib.request.urlopen(req) as r:
    print(r.status, r.read().decode())
"
```

Verified response (`200`):

```json
{"success":true,"message":"Email has been verified successfully","data":{"account":{"id":"...","email":"e2e-test-user@localhost.com","name":"E2E Test User"}}}
```

Confirm the account is now `ACTIVE` in the DB:

```bash
docker compose exec -T postgres psql -U synkora -d synkora -c \
  "SELECT email, status FROM accounts WHERE email='e2e-test-user@localhost.com';"
```

Verified: `status = ACTIVE`.

---

## Step 4 — Login (Now Succeeds)

```python
docker compose exec -T api python3 -c "
import urllib.request, json
payload = json.dumps({'email': 'e2e-test-user@localhost.com', 'password': 'Xk9#mQ7vLp2\$ZnR4'}).encode()
req = urllib.request.Request(
    'http://localhost:5001/console/api/auth/login',
    data=payload,
    headers={'Content-Type': 'application/json'},
    method='POST'
)
with urllib.request.urlopen(req) as r:
    d = json.loads(r.read())
    print('access_token=' + d['data']['access_token'][:20] + '...')
    print('refresh_token=' + d['data']['refresh_token'][:20] + '...')
"
```

Verified response shape (`200`):

```json
{"success":true,"data":{"access_token":"...","refresh_token":"...","token_type":"Bearer","expires_in":3600,"account_id":"...","tenant_id":"...","account":{"id":"...","email":"...","name":"...","status":"ACTIVE"},"tenants":[{"tenant_id":"...","tenant_name":"...","role":"OWNER","is_owner":true,"is_admin":true,"can_edit":true}]},"message":"Login successful"}
```

Both `access_token` and `refresh_token` are returned directly in the JSON body (in addition to
`refresh_token` being set as an HttpOnly cookie) — no need for a cookie jar to test the refresh flow.

If 2FA were enabled for this account, the response would instead be `200` with
`{"success": false, "requires_2fa": true, "temp_token": "..."}`.

---

## Step 5 — Call an Authenticated Endpoint (`/auth/me`)

```python
docker compose exec -T api python3 -c "
import urllib.request, json
TOKEN = '<paste access_token here>'
req = urllib.request.Request(
    'http://localhost:5001/console/api/auth/me',
    headers={'Authorization': f'Bearer {TOKEN}'}
)
with urllib.request.urlopen(req) as r:
    print(r.status, r.read().decode())
"
```

Verified: `200` with `data.account` and `data.tenants` (array of tenant memberships with role flags).

---

## Step 6 — Refresh the Access Token

The `refresh` endpoint accepts `refresh_token` in the request body (fallback path — the preferred
path for browser clients is the HttpOnly cookie set at login, sent automatically):

```python
docker compose exec -T api python3 -c "
import urllib.request, json

# Login to get a refresh_token
login_payload = json.dumps({'email': 'e2e-test-user@localhost.com', 'password': 'Xk9#mQ7vLp2\$ZnR4'}).encode()
login_req = urllib.request.Request(
    'http://localhost:5001/console/api/auth/login',
    data=login_payload,
    headers={'Content-Type': 'application/json'},
    method='POST'
)
with urllib.request.urlopen(login_req) as r:
    login_data = json.loads(r.read())['data']

refresh_payload = json.dumps({'refresh_token': login_data['refresh_token']}).encode()
refresh_req = urllib.request.Request(
    'http://localhost:5001/console/api/auth/refresh',
    data=refresh_payload,
    headers={'Content-Type': 'application/json'},
    method='POST'
)
with urllib.request.urlopen(refresh_req) as r:
    refresh_data = json.loads(r.read())['data']

print('login access_token :', login_data['access_token'][:20], '...')
print('refresh access_token:', refresh_data['access_token'][:20], '...')
"
```

Verified: both calls return `200` with `data.access_token`; the two tokens differ (new token issued
on refresh). Response message: `"Token refreshed successfully"`.

---

## Step 7 — Forgot Password → Reset Password → Old Session Invalidated

```python
docker compose exec -T api python3 -c "
import urllib.request, json
payload = json.dumps({'email': 'e2e-test-user@localhost.com'}).encode()
req = urllib.request.Request(
    'http://localhost:5001/console/api/auth/forgot-password',
    data=payload,
    headers={'Content-Type': 'application/json'},
    method='POST'
)
with urllib.request.urlopen(req) as r:
    print(r.status, r.read().decode())
"
```

Verified: `200` — `{"success":true,"message":"If the email exists, a password reset link has been sent."}`
(always the same message, whether or not the email exists — anti-enumeration).

Since SMTP isn't configured, generate the raw reset token in-process the same way the endpoint does
(this also writes the hashed token to the DB, exactly like the real flow):

```python
docker compose exec -T api python3 -c "
import asyncio
from sqlalchemy import select
from src.core.database import get_async_session_factory
from src.models import Account
from src.services.auth_service import AuthService

async def main():
    factory = get_async_session_factory()
    async with factory() as db:
        result = await db.execute(select(Account).filter_by(email='e2e-test-user@localhost.com'))
        account = result.scalar_one()
        _, raw_token = await AuthService.request_password_reset(db, account.email)
        print('RAW_RESET_TOKEN=' + raw_token)

asyncio.run(main())
"
```

Reset the password:

```python
docker compose exec -T api python3 -c "
import urllib.request, json
TOKEN = '<paste RAW_RESET_TOKEN here>'
payload = json.dumps({'token': TOKEN, 'new_password': 'Rq3\$vTn8pWy5#Bm2'}).encode()
req = urllib.request.Request(
    'http://localhost:5001/console/api/auth/reset-password',
    data=payload,
    headers={'Content-Type': 'application/json'},
    method='POST'
)
with urllib.request.urlopen(req) as r:
    print(r.status, r.read().decode())
"
```

Verified: `200` — `{"success":true,"message":"Password has been reset successfully"}`.

Confirm the **old** access token (from Step 4/6) is now rejected — password reset blacklists all
existing sessions for the account:

```python
docker compose exec -T api python3 -c "
import urllib.request, urllib.error
TOKEN = '<paste an access_token from BEFORE the reset>'
req = urllib.request.Request(
    'http://localhost:5001/console/api/auth/me',
    headers={'Authorization': f'Bearer {TOKEN}'}
)
try:
    with urllib.request.urlopen(req) as r:
        print(r.status, r.read().decode())
except urllib.error.HTTPError as e:
    print(e.code, e.read().decode())
"
```

Verified: `401` — `{"detail":"Token has been revoked"}`.

Confirm login with the **old** password now fails (`401`, `{"detail":"Invalid email or password"}`)
and login with the **new** password (`Rq3$vTn8pWy5#Bm2`) succeeds (`200`).

---

## Step 8 — Resend Verification (Anti-Enumeration Check)

```python
docker compose exec -T api python3 -c "
import urllib.request, json
for email in ['e2e-test-user@localhost.com', 'does-not-exist@localhost.com']:
    payload = json.dumps({'email': email}).encode()
    req = urllib.request.Request(
        'http://localhost:5001/console/api/auth/resend-verification',
        data=payload,
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    with urllib.request.urlopen(req) as r:
        print(email, '->', r.status, r.read().decode())
"
```

Verified: identical `200` response for both a real and a nonexistent email — confirms no
account-enumeration leak.

---

## Step 9 — Logout

```python
docker compose exec -T api python3 -c "
import urllib.request, json
TOKEN = '<paste a valid access_token>'
req = urllib.request.Request(
    'http://localhost:5001/console/api/auth/logout',
    data=b'{}',
    headers={'Authorization': f'Bearer {TOKEN}', 'Content-Type': 'application/json'},
    method='POST'
)
with urllib.request.urlopen(req) as r:
    print(r.status, r.read().decode())
"
```

Verified: `200` — `{"success":true,"message":"Logout successful"}`. A subsequent call to `/auth/me`
with the same token returns `401` — `{"detail":"Token has been revoked"}`.

---

## Cleanup

Delete the test account and its tenant (deleting the account does **not** cascade-delete the tenant
— confirmed by testing, so both rows must be removed explicitly):

```bash
docker compose exec -T postgres psql -U synkora -d synkora -c \
  "DELETE FROM accounts WHERE email='e2e-test-user@localhost.com'; DELETE FROM tenants WHERE name='E2E Test Org';"
```

---

## Endpoint Reference

| Purpose | Method | Path | Auth required |
|---------|--------|------|----------------|
| Register | POST | `/console/api/auth/register` | No |
| Login | POST | `/console/api/auth/login` | No |
| Verify email | POST | `/console/api/auth/verify-email` | No (token in body) |
| Resend verification | POST | `/console/api/auth/resend-verification` | No |
| Forgot password | POST | `/console/api/auth/forgot-password` | No |
| Reset password | POST | `/console/api/auth/reset-password` | No (token in body) |
| Refresh token | POST | `/console/api/auth/refresh` | Cookie or body `refresh_token` |
| Current account | GET | `/console/api/auth/me` | Bearer token |
| Switch tenant | POST | `/console/api/auth/switch-tenant` | Bearer token |
| Logout | POST | `/console/api/auth/logout` | Bearer token |

## Notes

- Password policy (`PasswordValidator`): min 12 chars, at least one uppercase, one lowercase, one
  digit, one special character. Also checked against the HaveIBeenPwned (HIBP) breach database on
  register/reset (fails open if HIBP is unreachable) — avoid common test passwords like
  `TestPass123!@#`, they get rejected with `422`.
- `docker compose exec -T postgres` assumes the Postgres service is reachable under that name — check
  `docker compose ps` if your local setup uses a different service/container name.
- Revoked/blacklisted tokens return `401` with `{"detail":"Token has been revoked"}`, distinct from
  the generic `{"detail":"Invalid email or password"}` used for bad login credentials.
