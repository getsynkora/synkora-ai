## ADDED Requirements

### Requirement: Callback validates state before any side effects
Every OAuth callback endpoint SHALL validate the state parameter against Redis as the very first operation, before exchanging the code or touching the database.

#### Scenario: Missing state parameter
- **WHEN** a callback request arrives without a `state` query parameter
- **THEN** the handler returns 400 Bad Request before attempting any token exchange

#### Scenario: Invalid or expired state
- **WHEN** `get_oauth_state(state)` returns None
- **THEN** the handler redirects to the error path with message "Invalid or expired state parameter"
- **THEN** no code exchange is attempted

### Requirement: Redirect URL is captured before async operations
Each callback handler SHALL capture `redirect_url` from state data into a local variable immediately after state retrieval, so error handlers can use it even after the state is consumed.

#### Scenario: Token exchange fails after state consumption
- **WHEN** `get_oauth_state(state)` succeeds (consuming the state)
- **AND** the subsequent code exchange fails with an exception
- **THEN** the error redirect uses the `redirect_url` from the consumed state, not the default path

#### Scenario: State is already consumed when error handler runs
- **WHEN** an error occurs mid-callback
- **THEN** the except block does NOT make a second Redis call to retrieve the state
- **THEN** the previously captured `redirect_url` variable is used instead

### Requirement: Redirect URLs are domain-validated
All redirect URLs — whether from state data or query parameters — SHALL pass `validate_redirect_url` before use. The validated URL SHALL be the one used in the redirect response.

#### Scenario: Redirect URL from state is within allowed domain
- **WHEN** the state contains `redirect_url = "https://app.example.com/oauth-apps"`
- **AND** the tenant's `APP_BASE_URL` is `"https://app.example.com"`
- **THEN** the callback redirects to that URL after success

#### Scenario: Redirect URL from state is external domain
- **WHEN** the state contains `redirect_url = "https://evil.com/steal"`
- **THEN** `sanitize_redirect_url` rejects it and uses the default path
- **THEN** the rejection is logged as a security warning

### Requirement: Error messages do not leak sensitive details
Error redirect URLs SHALL encode only sanitized, user-facing error strings. Internal exception messages, stack traces, and credential fragments SHALL NOT appear in redirect parameters.

#### Scenario: Code exchange fails with internal error
- **WHEN** the OAuth provider returns an error response
- **THEN** the `message` query parameter in the redirect contains a generic user-facing string
- **THEN** the raw exception message is logged server-side but not exposed in the redirect URL

#### Scenario: Decryption failure
- **WHEN** `decrypt_value(oauth_app.client_secret)` raises an exception
- **THEN** the callback returns 500 with message "Failed to decrypt OAuth credentials"
- **THEN** no key material or exception detail appears in the response body or redirect URL

### Requirement: IDOR protection on all callback authorize endpoints
Every `GET /<provider>/authorize` endpoint SHALL verify that the requested `oauth_app_id` belongs to the authenticated tenant (or is a platform app) before generating a state.

#### Scenario: Authorize with another tenant's app ID
- **WHEN** an authenticated user requests authorize with an `oauth_app_id` belonging to a different tenant
- **THEN** `_get_oauth_app_secure` returns None
- **THEN** the endpoint returns 404 without generating a state or auth URL
