import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  generateCodeVerifier,
  generateCodeChallenge,
  generateState,
  isTokenExpiringSoon,
  storePkceParams,
  loadPkceParams,
  clearPkceParams,
  storeSynkoraUrl,
  buildAuthUrl,
} from '@/lib/auth';

describe('PKCE helpers', () => {
  it('generates a code verifier of appropriate length', async () => {
    const verifier = await generateCodeVerifier();
    // Base64url of 48 bytes = 64 chars
    expect(verifier.length).toBeGreaterThanOrEqual(43);
    expect(verifier.length).toBeLessThanOrEqual(128);
    // Must be base64url characters only
    expect(verifier).toMatch(/^[A-Za-z0-9\-_]+$/);
  });

  it('generates a code challenge from verifier', async () => {
    const verifier = await generateCodeVerifier();
    const challenge = await generateCodeChallenge(verifier);
    expect(challenge.length).toBeGreaterThan(0);
    expect(challenge).toMatch(/^[A-Za-z0-9\-_]+$/);
    // Challenge is different from verifier
    expect(challenge).not.toBe(verifier);
  });

  it('generates a unique state each time', () => {
    const s1 = generateState();
    const s2 = generateState();
    expect(s1).not.toBe(s2);
    expect(s1.length).toBeGreaterThan(16);
  });

  it('produces consistent challenge for same verifier', async () => {
    const verifier = 'dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk';
    const c1 = await generateCodeChallenge(verifier);
    const c2 = await generateCodeChallenge(verifier);
    expect(c1).toBe(c2);
  });
});

describe('isTokenExpiringSoon', () => {
  it('returns true when token expires within buffer window', () => {
    const expiresAt = Date.now() + 30_000; // 30s from now
    expect(isTokenExpiringSoon(expiresAt, 60_000)).toBe(true);
  });

  it('returns false when token has plenty of time', () => {
    const expiresAt = Date.now() + 300_000; // 5min from now
    expect(isTokenExpiringSoon(expiresAt, 60_000)).toBe(false);
  });

  it('returns true when token is already expired', () => {
    const expiresAt = Date.now() - 1000;
    expect(isTokenExpiringSoon(expiresAt)).toBe(true);
  });
});

describe('PKCE session storage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    const sessionStore: Record<string, unknown> = {};
    (chrome.storage.session.set as ReturnType<typeof vi.fn>).mockImplementation((data: Record<string, unknown>) => {
      Object.assign(sessionStore, data);
      return Promise.resolve();
    });
    (chrome.storage.session.get as ReturnType<typeof vi.fn>).mockImplementation((keys: string[]) => {
      const result: Record<string, unknown> = {};
      keys.forEach((k) => { if (k in sessionStore) result[k] = sessionStore[k]; });
      return Promise.resolve(result);
    });
    (chrome.storage.session.remove as ReturnType<typeof vi.fn>).mockImplementation((keys: string[]) => {
      keys.forEach((k) => { delete sessionStore[k]; });
      return Promise.resolve();
    });
  });

  it('stores and retrieves PKCE params', async () => {
    await storePkceParams('test-verifier', 'test-state');
    const result = await loadPkceParams();
    expect(result).toEqual({ verifier: 'test-verifier', state: 'test-state' });
  });

  it('returns null when no PKCE params stored', async () => {
    const result = await loadPkceParams();
    expect(result).toBeNull();
  });

  it('clears PKCE params after use', async () => {
    await storePkceParams('test-verifier', 'test-state');
    await clearPkceParams();
    const result = await loadPkceParams();
    expect(result).toBeNull();
  });
});

describe('Synkora URL trust checks', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('stores HTTPS instance URLs', async () => {
    await storeSynkoraUrl('https://app.synkora.example/');
    expect(chrome.storage.local.set).toHaveBeenCalledWith({
      snkr_url: 'https://app.synkora.example',
    });
  });

  it('allows local HTTP development URLs', async () => {
    await storeSynkoraUrl('http://localhost:3000');
    expect(chrome.storage.local.set).toHaveBeenCalledWith({
      snkr_url: 'http://localhost:3000',
    });
  });

  it('rejects non-local HTTP instance URLs', async () => {
    await expect(storeSynkoraUrl('http://synkora.example')).rejects.toThrow(
      'Synkora URL must use HTTPS outside local development'
    );
    expect(chrome.storage.local.set).not.toHaveBeenCalled();
  });

  it('rejects insecure auth URL construction', async () => {
    await expect(buildAuthUrl('http://synkora.example')).rejects.toThrow(
      'Synkora URL must use HTTPS outside local development'
    );
  });
});
