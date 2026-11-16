import { afterEach, describe, expect, it, vi } from 'vitest';
import { messages, browserLanguageTag, currentLanguage, languageFrom, t, type MessageKey } from '@/lib/i18n';
import { streamChat } from '@/lib/api';

// The test setup defines `chrome` as a plain property, so it is assigned and restored.
const globals = globalThis as unknown as { chrome: unknown };
const originalChrome = globals.chrome;

function setBrowserLanguage(tag: string) {
  globals.chrome = { ...(originalChrome as object), i18n: { getUILanguage: () => tag } };
}

afterEach(() => {
  globals.chrome = originalChrome;
  vi.unstubAllGlobals();
});

describe('translations', () => {
  it('German has exactly the keys English has', () => {
    expect(Object.keys(messages.de).sort()).toEqual(Object.keys(messages.en).sort());
  });

  it('German keeps every {value} English uses, and is never empty', () => {
    const slots = (text: string) => [...text.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort();
    for (const key of Object.keys(messages.en) as MessageKey[]) {
      expect(slots(messages.de[key]), key).toEqual(slots(messages.en[key]));
      if (key !== 'canSeeAfter') expect(messages.de[key].trim(), key).not.toBe('');
    }
  });
});

describe('language', () => {
  it('maps browser tags to a language we have', () => {
    expect(languageFrom('de-AT')).toBe('de');
    expect(languageFrom('DE')).toBe('de');
    expect(languageFrom('en-GB')).toBe('en');
    expect(languageFrom('fr')).toBeNull();
    expect(languageFrom('')).toBeNull();
    expect(languageFrom(undefined)).toBeNull();
  });

  it("follows the browser's UI language, English when it is not translated", () => {
    setBrowserLanguage('de');
    expect(currentLanguage()).toBe('de');
    setBrowserLanguage('fr-FR');
    expect(currentLanguage()).toBe('en');
  });

  it('keeps the full tag for the API', () => {
    setBrowserLanguage('de-AT');

    expect(browserLanguageTag()).toBe('de-AT');
  });

  it('falls back to the page language when the extension API is missing', () => {
    globals.chrome = undefined;

    expect(typeof browserLanguageTag()).toBe('string');
    expect(browserLanguageTag().length).toBeGreaterThan(0);
  });
});

describe('t', () => {
  it('speaks the browser language and fills in values', () => {
    setBrowserLanguage('de');

    expect(t('connect')).toBe('Mit Synkora verbinden');
    expect(t('messageAgent', { name: 'Muse' })).toBe('Nachricht an Muse …');
    expect(t('fillMany', { count: 3 })).toBe('3 Felder ausfüllen');
  });

  it('speaks English otherwise', () => {
    setBrowserLanguage('en-US');

    expect(t('connect')).toBe('Connect with Synkora');
    expect(t('fillMany', { count: 3 })).toBe('Fill 3 fields');
    expect(t('errorPrefix', { message: 'x' })).toBe('Error: x');
  });

  it('can be asked for a specific language', () => {
    expect(t('settings', {}, 'de')).toBe('Einstellungen');
    expect(t('settings', {}, 'en')).toBe('Settings');
  });

  it('leaves a {value} alone when none is given', () => {
    expect(t('messageAgent', {}, 'en')).toBe('Message {name}…');
  });
});

describe('chat requests', () => {
  it("send the browser's language so the agent answers in it", async () => {
    setBrowserLanguage('de-DE');
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      body: new ReadableStream({ start: (c) => c.close() }),
    });
    vi.stubGlobal('fetch', fetchMock);

    await streamChat(
      { synkoraUrl: 'https://example.com', accessToken: 't', agentSlug: 'muse', message: 'Hallo', conversationId: undefined },
      new AbortController().signal,
    );

    const body = JSON.parse(fetchMock.mock.calls[0][1].body as string);
    expect(body.language).toBe('de-DE');
    expect(body.message).toBe('Hallo');
  });
});
