/**
 * PKCE auth helpers and token storage for the Synkora Chrome extension.
 *
 * Security model:
 * - Access token: chrome.storage.session (in-memory, cleared on browser close)
 * - Refresh token: chrome.storage.local (persisted, sandboxed to extension)
 * - Tokens never passed to content scripts
 * - All message handlers validate sender.id === chrome.runtime.id
 */

import type { AuthTokens } from '@/types';

const ACCESS_TOKEN_KEY = 'snkr_access_token';
const REFRESH_TOKEN_KEY = 'snkr_refresh_token';
const EXPIRES_AT_KEY = 'snkr_expires_at';
const SYNKORA_URL_KEY = 'snkr_url';
const API_URL_KEY = 'snkr_api_url';
const PKCE_VERIFIER_KEY = 'snkr_pkce_verifier';
const PKCE_STATE_KEY = 'snkr_pkce_state';

function assertTrustedSynkoraUrl(url: string): void {
  const parsed = new URL(url);
  const isLocalHttp = parsed.protocol === 'http:' && ['localhost', '127.0.0.1', '[::1]'].includes(parsed.hostname);
  if (parsed.protocol !== 'https:' && !isLocalHttp) {
    throw new Error('Synkora URL must use HTTPS outside local development');
  }
}

// ── PKCE helpers ──────────────────────────────────────────────────────────────

function base64UrlEncode(buffer: ArrayBuffer): string {
  return btoa(String.fromCharCode(...new Uint8Array(buffer)))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=/g, '');
}

export async function generateCodeVerifier(): Promise<string> {
  const array = new Uint8Array(48);
  crypto.getRandomValues(array);
  return base64UrlEncode(array.buffer);
}

export async function generateCodeChallenge(verifier: string): Promise<string> {
  const encoded = new TextEncoder().encode(verifier);
  const digest = await crypto.subtle.digest('SHA-256', encoded);
  return base64UrlEncode(digest);
}

export function generateState(): string {
  const array = new Uint8Array(32);
  crypto.getRandomValues(array);
  return base64UrlEncode(array.buffer);
}

// ── PKCE session storage (ephemeral — cleared on browser close) ───────────────

export async function storePkceParams(verifier: string, state: string): Promise<void> {
  await chrome.storage.session.set({
    [PKCE_VERIFIER_KEY]: verifier,
    [PKCE_STATE_KEY]: state,
  });
}

export async function loadPkceParams(): Promise<{ verifier: string; state: string } | null> {
  const result = await chrome.storage.session.get([PKCE_VERIFIER_KEY, PKCE_STATE_KEY]);
  const verifier = result[PKCE_VERIFIER_KEY] as string | undefined;
  const state = result[PKCE_STATE_KEY] as string | undefined;
  if (!verifier || !state) return null;
  return { verifier, state };
}

export async function clearPkceParams(): Promise<void> {
  await chrome.storage.session.remove([PKCE_VERIFIER_KEY, PKCE_STATE_KEY]);
}

// ── Token storage ─────────────────────────────────────────────────────────────

export async function storeTokens(tokens: AuthTokens): Promise<void> {
  // Access token: session storage (in-memory)
  await chrome.storage.session.set({
    [ACCESS_TOKEN_KEY]: tokens.accessToken,
    [EXPIRES_AT_KEY]: tokens.expiresAt,
  });
  // Refresh token: local storage (persisted)
  await chrome.storage.local.set({
    [REFRESH_TOKEN_KEY]: tokens.refreshToken,
  });
}

export async function loadAccessToken(): Promise<{ token: string; expiresAt: number } | null> {
  const result = await chrome.storage.session.get([ACCESS_TOKEN_KEY, EXPIRES_AT_KEY]);
  const token = result[ACCESS_TOKEN_KEY] as string | undefined;
  const expiresAt = result[EXPIRES_AT_KEY] as number | undefined;
  if (!token || !expiresAt) return null;
  return { token, expiresAt };
}

export async function loadRefreshToken(): Promise<string | null> {
  const result = await chrome.storage.local.get(REFRESH_TOKEN_KEY);
  return (result[REFRESH_TOKEN_KEY] as string | undefined) ?? null;
}

export async function clearTokens(): Promise<void> {
  await chrome.storage.session.remove([ACCESS_TOKEN_KEY, EXPIRES_AT_KEY]);
  await chrome.storage.local.remove(REFRESH_TOKEN_KEY);
}

export function isTokenExpiringSoon(expiresAt: number, bufferMs = 60_000): boolean {
  return Date.now() >= expiresAt - bufferMs;
}

// ── Synkora instance URL ──────────────────────────────────────────────────────

export async function storeSynkoraUrl(url: string): Promise<void> {
  const normalized = url.replace(/\/$/, '');
  assertTrustedSynkoraUrl(normalized);
  await chrome.storage.local.set({ [SYNKORA_URL_KEY]: normalized });
}

export async function loadSynkoraUrl(): Promise<string | null> {
  const result = await chrome.storage.local.get(SYNKORA_URL_KEY);
  return (result[SYNKORA_URL_KEY] as string | undefined) ?? null;
}

export async function storeApiUrl(url: string): Promise<void> {
  await chrome.storage.local.set({ [API_URL_KEY]: url.replace(/\/$/, '') });
}

export async function loadApiUrl(): Promise<string | null> {
  const result = await chrome.storage.local.get(API_URL_KEY);
  return (result[API_URL_KEY] as string | undefined) ?? null;
}

// ── Auth URL builder ──────────────────────────────────────────────────────────

export async function buildAuthUrl(synkoraUrl: string): Promise<{ url: string; state: string }> {
  assertTrustedSynkoraUrl(synkoraUrl);
  const verifier = await generateCodeVerifier();
  const challenge = await generateCodeChallenge(verifier);
  const state = generateState();

  await storePkceParams(verifier, state);

  const redirectUri = `https://${chrome.runtime.id}.chromiumapp.org/`;
  const params = new URLSearchParams({
    code_challenge: challenge,
    code_challenge_method: 'S256',
    state,
    redirect_uri: redirectUri,
  });

  return {
    url: `${synkoraUrl}/extension-auth?${params}`,
    state,
  };
}

// ── Token exchange ────────────────────────────────────────────────────────────

export async function exchangeCodeForTokens(
  synkoraUrl: string,
  code: string,
  returnedState: string,
  apiUrl?: string,
): Promise<AuthTokens> {
  assertTrustedSynkoraUrl(synkoraUrl);
  const pkce = await loadPkceParams();
  if (!pkce) throw new Error('No PKCE params found — auth session expired');
  if (pkce.state !== returnedState) throw new Error('State mismatch — possible CSRF attack');

  // Use the API URL returned in the callback (stored during auth), falling back to synkoraUrl
  const resolvedApiUrl = apiUrl ?? (await loadApiUrl()) ?? synkoraUrl;
  const redirectUri = `https://${chrome.runtime.id}.chromiumapp.org/`;
  const resp = await fetch(`${resolvedApiUrl}/console/api/auth/extension/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      code,
      code_verifier: pkce.verifier,
      redirect_uri: redirectUri,
    }),
  });

  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail ?? 'Token exchange failed');
  }

  const data = await resp.json() as {
    access_token: string;
    refresh_token: string;
    expires_in: number;
  };

  const tokens: AuthTokens = {
    accessToken: data.access_token,
    refreshToken: data.refresh_token,
    expiresAt: Date.now() + data.expires_in * 1000,
  };

  await clearPkceParams();
  await storeTokens(tokens);
  return tokens;
}

// ── Token refresh ─────────────────────────────────────────────────────────────

export async function refreshAccessToken(synkoraUrl: string): Promise<AuthTokens | null> {
  assertTrustedSynkoraUrl(synkoraUrl);
  const refreshToken = await loadRefreshToken();
  if (!refreshToken) return null;

  const resolvedApiUrl = (await loadApiUrl()) ?? synkoraUrl;
  const resp = await fetch(`${resolvedApiUrl}/console/api/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });

  if (!resp.ok) {
    await clearTokens();
    return null;
  }

  const data = await resp.json() as {
    access_token: string;
    refresh_token: string;
    expires_in: number;
  };

  const tokens: AuthTokens = {
    accessToken: data.access_token,
    refreshToken: data.refresh_token,
    expiresAt: Date.now() + data.expires_in * 1000,
  };

  await storeTokens(tokens);
  return tokens;
}
