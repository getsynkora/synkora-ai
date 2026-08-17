## ADDED Requirements

### Requirement: State service uses async Redis
The OAuth state service SHALL use async Redis operations exclusively, never blocking the event loop with synchronous Redis calls.

#### Scenario: State created during OAuth initiation
- **WHEN** `create_oauth_state()` is called inside an async FastAPI handler
- **THEN** the Redis write uses `await redis.setex(...)` (async client) and does not block the event loop

#### Scenario: State retrieved during OAuth callback
- **WHEN** `get_oauth_state()` is called inside an async FastAPI handler
- **THEN** the Redis get-and-delete uses `await redis.getdel(...)` (async client)

### Requirement: State token is cryptographically secure
The system SHALL generate OAuth state tokens using `secrets.token_urlsafe(32)`, producing at least 256 bits of entropy.

#### Scenario: State token generated
- **WHEN** `create_oauth_state()` is called
- **THEN** the returned state token is at least 43 characters (URL-safe base64 of 32 bytes)

### Requirement: State is single-use
The system SHALL consume (delete) the state token atomically on first successful retrieval, preventing replay attacks.

#### Scenario: Callback reuses state
- **WHEN** a callback endpoint calls `get_oauth_state(state)` twice with the same token
- **THEN** the second call returns None

#### Scenario: State retrieved atomically
- **WHEN** `get_oauth_state(state)` is called
- **THEN** the Redis operation is a single atomic `GETDEL`, not a separate GET + DEL

### Requirement: State TTL is not extended on update
The system SHALL preserve the original expiry time when updating state with additional fields (e.g., PKCE code_verifier). The TTL SHALL NOT be reset to a new 10-minute window.

#### Scenario: PKCE code_verifier stored after state creation
- **WHEN** `update_oauth_state(state, {"code_verifier": "..."})` is called
- **THEN** the remaining TTL on the Redis key is the original 10 minutes minus elapsed time, not a fresh 10 minutes

#### Scenario: Update on nearly-expired state
- **WHEN** `update_oauth_state` is called on a state with less than 1 second remaining
- **THEN** the function returns False (treated as expired)

### Requirement: State is tied to a single tenant
The state data stored in Redis SHALL include `tenant_id` for all authenticated OAuth initiations. Callbacks SHALL verify that the tenant context matches the state's `tenant_id`.

#### Scenario: Authenticated initiation stores tenant
- **WHEN** `POST /api/v1/oauth/initiate` is called with a valid JWT
- **THEN** the state data stored in Redis contains the JWT's `tenant_id`

#### Scenario: Callback uses state tenant_id
- **WHEN** a callback exchanges code for token for a platform app
- **THEN** the tenant clone is created using only `state_data["tenant_id"]`, never a request-level parameter
