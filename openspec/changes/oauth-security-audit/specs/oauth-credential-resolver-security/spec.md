## ADDED Requirements

### Requirement: OAuthApp lookup in resolver includes tenant filter
When `CredentialResolver` fetches an `OAuthApp` for runtime use, the query SHALL include a tenant guard: either `OAuthApp.tenant_id == context.tenant_id` OR `OAuthApp.is_platform_app == True`. Raw lookups by ID alone are not permitted.

#### Scenario: Agent tool references a valid tenant-owned OAuthApp
- **WHEN** the credential resolver fetches `OAuthApp.id = X` for `tenant_id = T`
- **THEN** the query filters `(OAuthApp.tenant_id == T) OR (OAuthApp.is_platform_app == True)`
- **THEN** if app X belongs to a different tenant, it is not returned

#### Scenario: Agent tool references a platform app
- **WHEN** the credential resolver fetches a platform OAuthApp (`is_platform_app=True`)
- **THEN** the app is returned regardless of `tenant_id` (platform apps are globally accessible)

#### Scenario: context.tenant_id is None in background task
- **WHEN** the resolver runs in a background task context without a tenant_id
- **THEN** the resolver restricts access to platform apps only, raising an error for tenant-owned apps

### Requirement: User-level token takes priority over app-level token
The credential resolver SHALL return the current user's personal token (from `UserOAuthToken`) before falling back to the app-level token on `OAuthApp`.

#### Scenario: Both user and app tokens exist
- **WHEN** a user has a `UserOAuthToken` for `oauth_app_id = X`
- **AND** the `OAuthApp` also has an `access_token`
- **THEN** the resolver returns the user's token, not the app token

#### Scenario: User token absent, app token present
- **WHEN** no `UserOAuthToken` exists for the current user and `oauth_app_id = X`
- **THEN** the resolver falls back to the app-level `OAuthApp.access_token`

### Requirement: Raw credentials are never returned to callers
The credential resolver SHALL return authenticated client objects, not raw decrypted tokens or credentials. Token strings are decrypted internally and consumed immediately to construct the client.

#### Scenario: GitHub client resolution
- **WHEN** a tool calls `get_github_client(tool_name)`
- **THEN** the return value is a `Github` client object
- **THEN** no method on `CredentialResolver` returns a raw token string to external callers

#### Scenario: Failed credential resolution
- **WHEN** no valid token is found for a provider
- **THEN** the resolver returns None (not an exception, not an empty token)
- **THEN** the tool logs a warning and skips the operation

### Requirement: Token refresh is attempted for providers with known expiry
For providers that issue short-lived access tokens with refresh grants (Google, Jira, Zoom, HubSpot, Salesforce, Intercom), the resolver SHALL attempt a token refresh when `token_expires_at` is in the past before returning a client.

#### Scenario: Expired Google Calendar token with valid refresh token
- **WHEN** `OAuthApp.token_expires_at < now` and `OAuthApp.refresh_token` is set
- **THEN** the resolver calls the provider's `refresh_token()` method
- **THEN** the new access token is persisted to `OAuthApp.access_token` and `token_expires_at`
- **THEN** a client is created with the refreshed token

#### Scenario: Refresh token exchange fails
- **WHEN** the provider rejects the refresh token (e.g., revoked)
- **THEN** the resolver logs a warning and returns None (does not return the expired token)
