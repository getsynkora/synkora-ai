/**
 * Secure Token Storage
 *
 * Storage strategy:
 *   - Access token  → in-memory only (never touches storage — XSS-safe)
 *   - Refresh token → HttpOnly cookie set by the backend (JS-unreachable)
 *
 * The browser automatically sends the HttpOnly refresh token cookie to
 * /console/api/auth/refresh (the only path it is scoped to).  No client-side
 * code can read, forge, or exfiltrate it.
 *
 * Flow:
 *   Login  → backend sets HttpOnly cookie; SPA stores access token in memory.
 *   Refresh → SPA calls /refresh with credentials:'include'; browser attaches
 *             cookie; backend validates + rotates it; returns new access token.
 *   Logout → backend clears the cookie; SPA clears memory.
 */

// ---------------------------------------------------------------------------
// In-memory access token (not persisted — cleared on page refresh / tab close)
// ---------------------------------------------------------------------------
let _accessToken: string | null = null
let _tokenExpiry: number | null = null

class SecureTokenStorage {
  /**
   * Store the access token in memory after login or token refresh.
   * The refresh token is handled entirely by the backend cookie — never stored here.
   */
  storeTokens(tokens: {
    access_token: string
    refresh_token?: string  // accepted but ignored — lives in HttpOnly cookie
    expires_in?: number
  }): void {
    _accessToken = tokens.access_token
    _tokenExpiry = Date.now() + ((tokens.expires_in ?? 3600) * 1000)
  }

  /** Return the in-memory access token, or null if missing / expired. */
  getAccessToken(): string | null {
    if (!_accessToken) return null
    if (_tokenExpiry && Date.now() > _tokenExpiry) {
      _accessToken = null
      _tokenExpiry = null
      return null
    }
    return _accessToken
  }

  /** True when the access token is missing or within 5 minutes of expiry. */
  isTokenExpired(): boolean {
    if (!_accessToken || !_tokenExpiry) return true
    return (_tokenExpiry - 300_000) <= Date.now()
  }

  /** Clear the in-memory access token. The HttpOnly cookie is cleared by the backend on logout. */
  clearTokens(): void {
    _accessToken = null
    _tokenExpiry = null

    // Remove any legacy localStorage tokens left over from older versions
    if (typeof window !== 'undefined') {
      try {
        ;['access_token', 'refresh_token', 'synkora_access', 'synkora_refresh', 'synkora_expires'].forEach(
          (k) => localStorage.removeItem(k)
        )
      } catch {
        // Ignore storage errors
      }
    }
  }

  /**
   * Refresh the access token.
   * Sends credentials:'include' so the browser attaches the HttpOnly refresh
   * token cookie automatically — no token value is passed in the request body.
   * On success the backend also rotates the cookie (old token invalidated).
   */
  async refreshAccessToken(): Promise<boolean> {
    const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:5001'
    try {
      const response = await fetch(`${API_URL}/console/api/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',  // browser sends the HttpOnly cookie
        body: JSON.stringify({}), // empty body — token comes from cookie
      })

      if (!response.ok) throw new Error(`Refresh failed: ${response.status}`)

      const data = await response.json()
      if (data.success && data.data?.access_token) {
        this.storeTokens({
          access_token: data.data.access_token,
          expires_in: data.data.expires_in,
        })
        return true
      }
    } catch (err) {
      console.error('Token refresh failed:', err)
    }

    this.clearTokens()
    return false
  }

  /**
   * Clean up any legacy localStorage tokens from older storage formats.
   * Runs once on app init.
   */
  migrateFromLocalStorage(): void {
    if (typeof window === 'undefined') return
    try {
      ;['access_token', 'refresh_token', 'synkora_access', 'synkora_refresh', 'synkora_expires'].forEach(
        (k) => localStorage.removeItem(k)
      )
    } catch {
      // Ignore errors
    }
  }
}

export const secureStorage = new SecureTokenStorage()

// ---------------------------------------------------------------------------
// App initialisation helper (call once in the root layout)
// ---------------------------------------------------------------------------

export function initializeSecureStorage(): void {
  if (typeof window === 'undefined') return

  // Migrate any existing localStorage tokens and wipe them
  secureStorage.migrateFromLocalStorage()

  // Proactively refresh when the tab regains focus if the access token is near expiry.
  // We can't check if the HttpOnly cookie exists from JS — just attempt the refresh;
  // it succeeds silently if the cookie is present, fails gracefully if not.
  let refreshInterval: ReturnType<typeof setInterval> | null = null

  const checkAndRefresh = () => {
    if (!secureStorage.isTokenExpired()) return
    secureStorage.refreshAccessToken().then((success) => {
      if (!success && refreshInterval !== null) {
        // No refresh cookie — stop polling. Dashboard layout handles per-route auth guards.
        clearInterval(refreshInterval)
        refreshInterval = null
      }
    })
  }

  refreshInterval = setInterval(checkAndRefresh, 5 * 60 * 1000)
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) checkAndRefresh()
  })
}

// ---------------------------------------------------------------------------
// React hook
// ---------------------------------------------------------------------------

export function useSecureAuth() {
  return {
    storeTokens: (tokens: { access_token: string; refresh_token?: string; expires_in?: number }) =>
      secureStorage.storeTokens(tokens),
    getAccessToken: () => secureStorage.getAccessToken(),
    isAuthenticated: () => !secureStorage.isTokenExpired(),
    logout: () => {
      secureStorage.clearTokens()
      if (typeof window !== 'undefined') window.location.href = '/signin'
    },
    refreshToken: () => secureStorage.refreshAccessToken(),
  }
}
