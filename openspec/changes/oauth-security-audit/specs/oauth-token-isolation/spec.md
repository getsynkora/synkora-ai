## ADDED Requirements

### Requirement: Platform app token never stored on shared row
When an OAuth callback completes for a platform app, the system SHALL store the access token on a tenant-owned clone row, never on the shared platform app row.

#### Scenario: First-time platform app connection
- **WHEN** a tenant connects a platform app for the first time
- **THEN** a new `OAuthApp` clone is created with `tenant_id = <tenant>` and `is_platform_app = False`
- **THEN** the access token is written to the clone, not to the original platform app row

#### Scenario: Subsequent platform app connection
- **WHEN** a tenant reconnects an already-cloned platform app
- **THEN** the existing clone is reused (no duplicate created)
- **THEN** only the `access_token` field is updated on the clone

### Requirement: Platform clone lookup is type-safe
The system SHALL store `config["platform_app_id"]` as a string and query it as a string, preventing duplicate clones due to integer vs string JSON type mismatch.

#### Scenario: Clone created with consistent type
- **WHEN** `_get_or_create_tenant_clone` creates a new clone
- **THEN** `config["platform_app_id"]` is stored as `str(platform_app.id)`

#### Scenario: Clone lookup handles legacy integer values
- **WHEN** looking up an existing clone
- **THEN** the query matches both `"42"` and `42` stored values (cast-safe comparison)

### Requirement: App-level and user-level tokens are isolated
Access tokens stored in `UserOAuthToken` SHALL be scoped to a single `(account_id, oauth_app_id)` pair. No query SHALL return a user token from a different tenant.

#### Scenario: User token lookup scoped to tenant
- **WHEN** `CredentialResolver._get_user_token_record` falls back to tenant-scoped lookup
- **THEN** it JOINs through `TenantAccountJoin` and filters by `TenantAccountJoin.tenant_id == context.tenant_id`

#### Scenario: User token from different tenant is never returned
- **WHEN** two users in different tenants have tokens for the same `oauth_app_id`
- **THEN** the resolver returns only the token belonging to the current tenant's user

### Requirement: Tokens are encrypted at rest
All OAuth tokens (access_token, refresh_token, api_token, client_secret) stored in the database SHALL be encrypted with Fernet before write and decrypted only at runtime.

#### Scenario: Token written to database
- **WHEN** a callback stores an access token via `encrypt_value(token)`
- **THEN** the raw plaintext token is never persisted to the database column

#### Scenario: Token serialized in API response
- **WHEN** `OAuthApp.to_dict()` is called
- **THEN** the response contains `has_access_token: bool`, never the token value itself

### Requirement: Disabled platform providers are not accessible
If a tenant has a provider listed in `disabled_platform_oauth_providers`, the system SHALL return None/404 for that platform app, not fall back to another tenant's configuration.

#### Scenario: Disabled provider lookup
- **WHEN** a tenant's `disabled_platform_oauth_providers` includes `"github"`
- **THEN** `get_oauth_app_from_db(..., provider="github", include_platform_apps=True)` raises 404
