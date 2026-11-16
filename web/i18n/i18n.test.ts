import { readFileSync, readdirSync } from 'node:fs'
import path from 'node:path'
import { describe, expect, it } from 'vitest'
import {
  defaultLocale,
  localeFromAcceptLanguage,
  locales,
  normalizeLocale,
  resolveLocale,
} from './config'

const ROOT = path.join(__dirname, '..')
const MESSAGES_DIR = path.join(ROOT, 'messages')

type Messages = { [key: string]: string | Messages }

function load(locale: string): Messages {
  return JSON.parse(readFileSync(path.join(MESSAGES_DIR, `${locale}.json`), 'utf8'))
}

/** "auth.signin.title" -> text, for every leaf. */
function flatten(messages: Messages, prefix = ''): Record<string, string> {
  const out: Record<string, string> = {}
  for (const [key, value] of Object.entries(messages)) {
    const name = prefix ? `${prefix}.${key}` : key
    if (typeof value === 'string') out[name] = value
    else Object.assign(out, flatten(value, name))
  }
  return out
}

/** The variables and tags a message uses: {name}, <b>…</b>, plural/select arguments. */
function placeholders(text: string): string[] {
  const names = new Set<string>()
  for (const match of text.matchAll(/\{(\w+)(?:,[^}]*)?/g)) names.add(match[1])
  for (const match of text.matchAll(/<(\w+)>/g)) names.add(`<${match[1]}>`)
  return [...names].sort()
}

describe('locale resolution', () => {
  it('normalizes regional and mixed-case codes', () => {
    expect(normalizeLocale('de-AT')).toBe('de')
    expect(normalizeLocale('DE')).toBe('de')
    expect(normalizeLocale('en_US')).toBe('en')
  })

  it('rejects languages without a translation', () => {
    for (const value of ['fr', '', undefined, null, 5, 'german', 'de; x']) {
      expect(normalizeLocale(value)).toBeNull()
    }
  })

  it('reads the best language from Accept-Language', () => {
    expect(localeFromAcceptLanguage('de-DE,de;q=0.9,en;q=0.8')).toBe('de')
    expect(localeFromAcceptLanguage('fr,de;q=0.7,en;q=0.5')).toBe('de')
    expect(localeFromAcceptLanguage('en;q=0.4, de;q=0.9')).toBe('de')
    expect(localeFromAcceptLanguage('fr, es')).toBeNull()
    expect(localeFromAcceptLanguage('de;q=0')).toBeNull()
    expect(localeFromAcceptLanguage('')).toBeNull()
    expect(localeFromAcceptLanguage(null)).toBeNull()
  })

  it('prefers the saved choice, then the browser, then English', () => {
    expect(resolveLocale({ cookie: 'de', acceptLanguage: 'en' })).toBe('de')
    expect(resolveLocale({ cookie: 'en', acceptLanguage: 'de' })).toBe('en')
    expect(resolveLocale({ cookie: undefined, acceptLanguage: 'de-CH' })).toBe('de')
    expect(resolveLocale({ cookie: 'fr', acceptLanguage: 'de' })).toBe('de')
    expect(resolveLocale({})).toBe(defaultLocale)
  })
})

describe('message files', () => {
  const english = flatten(load('en'))

  it('has a file for every supported language', () => {
    const files = readdirSync(MESSAGES_DIR).map((f) => f.replace('.json', '')).sort()
    expect(files).toEqual([...locales].sort())
  })

  for (const locale of locales.filter((l) => l !== 'en')) {
    const translated = flatten(load(locale))

    it(`${locale} has exactly the keys English has`, () => {
      expect(Object.keys(translated).sort()).toEqual(Object.keys(english).sort())
    })

    it(`${locale} keeps every variable and tag English uses`, () => {
      for (const [key, text] of Object.entries(english)) {
        expect(placeholders(translated[key]), `placeholders of ${key}`).toEqual(placeholders(text))
      }
    })

    it(`${locale} has no empty text`, () => {
      for (const [key, text] of Object.entries(translated)) {
        expect(text.trim(), key).not.toBe('')
      }
    })
  }
})

describe('translation keys used in the code', () => {
  const files = [
    'app/(auth)/signin/page.tsx',
    'app/(auth)/signup/page.tsx',
    'app/(auth)/forgot-password/page.tsx',
    'app/(auth)/reset-password/page.tsx',
    'app/(auth)/verify-email/page.tsx',
    'app/(auth)/accept-invite/page.tsx',
    'app/(auth)/extension-auth/page.tsx',
    'app/(dashboard)/agents/page.tsx',
    'components/i18n/LanguageSwitcher.tsx',
    'components/auth/AuthPageFrame.tsx',
    'components/social-auth/SocialLoginButton.tsx',
    'components/layout/Header.tsx',
    'components/chat/components/ChatMessage.tsx',
    'components/chat/components/ChatMessages.tsx',
    'app/share/[token]/page.tsx',
    'app/share/[token]/SharedChatView.tsx',
    'app/(public)/creators/[username]/page.tsx',
    'app/(public)/a/[slug]/AnimatedLanding.tsx',
  ]
  const english = flatten(load('en'))

  for (const file of files) {
    it(`${file} only uses keys that exist`, () => {
      const source = readFileSync(path.join(ROOT, file), 'utf8')
      const namespaces = [...source.matchAll(/(?:useTranslations|getTranslations)\('([\w.]+)'\)/g)].map((m) => m[1])
      expect(namespaces.length, 'uses useTranslations or getTranslations').toBeGreaterThan(0)

      const keys = [...source.matchAll(/\bt{1,2}(?:\.rich)?\(\s*'([\w.]+)'/g)].map((m) => m[1])
      expect(keys.length).toBeGreaterThan(0)
      for (const key of keys) {
        const found = namespaces.some((ns) => `${ns}.${key}` in english)
        expect(found, `${file}: missing key "${key}" in ${namespaces.join(', ')}`).toBe(true)
      }
    })
  }
})
