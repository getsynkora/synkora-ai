# Zendesk + Zoho CRM OAuth Integration Design

## Overview

Add Zendesk and Zoho CRM as connectable OAuth providers on the `/oauth-apps` integrations page. Jira is already fully implemented and requires no changes.

Both providers follow the existing GitLab/ClickUp pattern: tenant admin creates an OAuth app with provider credentials and any provider-specific config (subdomain for Zendesk, data_center for Zoho CRM), then users connect their individual accounts via the standard OAuth 2.0 authorization_code flow.

---

## Architecture

Each provider requires four things:
1. **OAuth service class** (`api/src/services/oauth/`) — wraps the provider's token exchange, user info, and refresh flows
2. **OAuth controller** (`api/src/controllers/oauth/`) — `authorize` + `callback` FastAPI endpoints
3. **Registration** in `__init__.py` and the `initiate_oauth` dispatcher in `base.py`
4. **Frontend config** in `oauth-apps/page.tsx` (`PROVIDER_CONFIG`) and `create/page.tsx` (`PROVIDERS` list)

---

## Zendesk

### Auth Methods
- **OAuth 2.0** (primary) — standard `authorization_code` grant
- **API token** (secondary) — Zendesk supports basic auth with email/token; stored as `api_token` auth method

### OAuth URLs (all subdomain-dependent)
- Authorize: `https://{subdomain}.zendesk.com/oauth/authorizations/new`
- Token: `https://{subdomain}.zendesk.com/oauth/tokens`
- User info: `https://{subdomain}.zendesk.com/api/v2/users/me.json`

### Config
- `config.subdomain` — stored in `OAuthApp.config` at creation time (same as GitLab's `base_url` pattern)
- Subdomain is the part before `.zendesk.com` (e.g. `mycompany` from `mycompany.zendesk.com`)

### Scopes
Default: `read write`

### Redirect URI
`{API_URL}/api/v1/oauth/zendesk/callback`

### Token storage
- App-level: stored on `OAuthApp.access_token` (no refresh token — Zendesk tokens don't expire)
- User-level: stored in `UserOAuthToken`

---

## Zoho CRM

### Auth Method
- **OAuth 2.0 only** — `authorization_code` grant with refresh token support

### OAuth URLs (data-center-dependent)
- Authorize: `https://accounts.zoho.{dc}/oauth/v2/auth`
- Token: `https://accounts.zoho.{dc}/oauth/v2/token`
- Revoke: `https://accounts.zoho.{dc}/oauth/v2/token/revoke`
- User info: `https://accounts.zoho.{dc}/oauth/user/info`

### Config
- `config.data_center` — one of `com` (default), `eu`, `in`, `com.au`, `jp`
- Stored in `OAuthApp.config` at creation time

### Scopes
Default: `ZohoCRM.modules.ALL ZohoCRM.settings.ALL ZohoCRM.users.READ ZohoCRM.org.READ offline_access`

### Redirect URI
`{API_URL}/api/v1/oauth/zoho/callback`

### Token storage
- Access token + refresh token stored encrypted
- `token_expires_at` set from `expires_in` field in token response

---

## Backend

### New Files

#### `api/src/services/oauth/zendesk_oauth.py`
```python
class ZendeskOAuth:
    def __init__(self, client_id, client_secret, redirect_uri, subdomain)
    def get_authorization_url(self, state, scopes) -> str
    async def get_access_token(self, code) -> dict
    async def get_user_info(self, token) -> dict
    async def refresh_token(self, refresh_token) -> dict  # no-op, tokens don't expire
    async def revoke_token(self, token) -> bool
```

#### `api/src/services/oauth/zoho_crm_oauth.py`
```python
class ZohoCRMOAuth:
    def __init__(self, client_id, client_secret, redirect_uri, data_center="com")
    def get_authorization_url(self, state, scopes) -> str
    async def get_access_token(self, code) -> dict
    async def get_user_info(self, token) -> dict
    async def refresh_token(self, refresh_token) -> dict
    async def revoke_token(self, token) -> bool
```

#### `api/src/controllers/oauth/zendesk.py`
- `GET /zendesk/authorize` — reads `subdomain` from `oauth_app.config`, builds auth URL, Redis state
- `GET /zendesk/callback` — exchanges code, stores token, redirects

#### `api/src/controllers/oauth/zoho.py`
- `GET /zoho/authorize` — reads `data_center` from `oauth_app.config` (default `com`), builds auth URL
- `GET /zoho/callback` — exchanges code, stores access + refresh tokens, redirects

### Modified Files

#### `api/src/controllers/oauth/__init__.py`
- Import and include `zendesk_router` and `zoho_router`

#### `api/src/controllers/oauth/base.py` — `initiate_oauth`
Add dispatch cases:
```python
elif provider == "zendesk":
    subdomain = (oauth_app.config or {}).get("subdomain", "")
    oauth = ZendeskOAuth(client_id, client_secret, redirect_uri, subdomain)
    auth_url = oauth.get_authorization_url(state, scopes)
elif provider == "zoho_crm":
    dc = (oauth_app.config or {}).get("data_center", "com")
    oauth = ZohoCRMOAuth(client_id, client_secret, redirect_uri, dc)
    auth_url = oauth.get_authorization_url(state, scopes)
```

---

## Frontend

### `web/app/(dashboard)/oauth-apps/page.tsx` — `PROVIDER_CONFIG`

Add entries:
```ts
zendesk: {
  name: 'Zendesk',
  icon: <svg ...>,  // Zendesk "Z" logo in #03363D green
  color: 'text-[#03363D]',
  bgColor: 'bg-green-50',
  borderColor: 'border-green-200',
  description: 'Tickets, users, and support conversations',
  setupUrl: 'https://developer.zendesk.com/documentation/live-chat/getting-started/oauth-authentication/',
}
zoho_crm: {
  name: 'Zoho CRM',
  icon: <svg ...>,  // Zoho red/orange logo
  color: 'text-[#E42527]',
  bgColor: 'bg-red-50',
  borderColor: 'border-red-200',
  description: 'Contacts, leads, deals, and CRM data',
  setupUrl: 'https://www.zoho.com/crm/developer/docs/api/v6/oauth-overview.html',
}
```

### `web/app/(dashboard)/oauth-apps/create/page.tsx` — `PROVIDERS` list

Add entries with config fields rendered inline (same as GitLab's `base_url` field):

**Zendesk:**
```ts
{
  value: 'zendesk',
  label: 'Zendesk',
  supportsOAuth: true,
  supportsApiToken: true,
  defaultScopes: ['read', 'write'],
  redirectUri: `${API_URL}/api/v1/oauth/zendesk/callback`,
  setupGuide: 'https://developer.zendesk.com/documentation/',
  configFields: [
    { key: 'subdomain', label: 'Zendesk Subdomain', placeholder: 'mycompany', required: true,
      hint: 'The part before .zendesk.com in your URL' }
  ]
}
```

**Zoho CRM:**
```ts
{
  value: 'zoho_crm',
  label: 'Zoho CRM',
  supportsOAuth: true,
  supportsApiToken: false,
  defaultScopes: ['ZohoCRM.modules.ALL', 'ZohoCRM.settings.ALL', 'ZohoCRM.users.READ', 'ZohoCRM.org.READ', 'offline_access'],
  redirectUri: `${API_URL}/api/v1/oauth/zoho/callback`,
  setupGuide: 'https://www.zoho.com/crm/developer/docs/',
  configFields: [
    { key: 'data_center', label: 'Data Center', type: 'select',
      options: ['com','eu','in','com.au','jp'], default: 'com',
      hint: 'Choose the region where your Zoho account is hosted' }
  ]
}
```

The create page already conditionally renders `config.base_url` for GitLab — the same conditional rendering approach is used for `config.subdomain` and `config.data_center`.

---

## Error Handling

- Missing `subdomain` in Zendesk config: raise `HTTPException(400, "Zendesk subdomain not configured")`
- Missing/invalid `data_center` in Zoho config: default to `com`
- Token exchange failure: raise `ValueError` (consistent with existing providers)
- Zendesk API token: stored via existing `api_token` auth method path — no new OAuth flow needed

---

## Testing

- Unit: `ZendeskOAuth.get_authorization_url()` builds correct subdomain URL
- Unit: `ZohoCRMOAuth.get_authorization_url()` builds correct data-center URL
- Unit: `ZohoCRMOAuth` token exchange parses `expires_in` correctly
- Integration: `GET /api/v1/oauth/zendesk/authorize` returns redirect with correct state
- Integration: `GET /api/v1/oauth/zoho/authorize` returns redirect with correct data-center URL
