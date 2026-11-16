/**
 * Languages the dashboard is available in, and how one is picked.
 *
 * The choice lives in a cookie (no language in the URL, so links stay the same),
 * is saved to the account when signed in, and starts from the browser's language.
 * To add a language: add its code here and a file in messages/.
 */
export const locales = ['en', 'de'] as const
export type Locale = (typeof locales)[number]

export const defaultLocale: Locale = 'en'
export const LOCALE_COOKIE = 'NEXT_LOCALE'

/** Names shown in the language picker, each written in its own language. */
export const localeNames: Record<Locale, string> = {
  en: 'English',
  de: 'Deutsch',
}

/** "de-AT" -> "de"; null when the language is not one we have. */
export function normalizeLocale(value: unknown): Locale | null {
  if (typeof value !== 'string') return null
  const language = value.trim().toLowerCase().split(/[-_]/)[0]
  return (locales as readonly string[]).includes(language) ? (language as Locale) : null
}

/** The best supported language in an Accept-Language header. */
export function localeFromAcceptLanguage(header: string | null | undefined): Locale | null {
  if (!header) return null
  const ranked = header
    .split(',')
    .slice(0, 20)
    .map((part, position) => {
      const [tag, ...params] = part.trim().split(';')
      const q = params.map((p) => p.trim()).find((p) => p.startsWith('q='))
      return { locale: normalizeLocale(tag), quality: q ? Number(q.slice(2)) : 1, position }
    })
    .filter((entry): entry is { locale: Locale; quality: number; position: number } =>
      entry.locale !== null && entry.quality > 0,
    )
    .sort((a, b) => b.quality - a.quality || a.position - b.position)
  return ranked[0]?.locale ?? null
}

/** The language to show: the saved choice, else the browser's, else English. */
export function resolveLocale(input: { cookie?: string | null; acceptLanguage?: string | null }): Locale {
  return (
    normalizeLocale(input.cookie) ?? localeFromAcceptLanguage(input.acceptLanguage) ?? defaultLocale
  )
}
