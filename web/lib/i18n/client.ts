import { LOCALE_COOKIE, type Locale } from '@/i18n/config'

/** Remembers the language in this browser for a year. */
export function saveLocaleCookie(locale: Locale) {
  document.cookie = `${LOCALE_COOKIE}=${locale}; path=/; max-age=31536000; samesite=lax`
}

export function hasLocaleCookie(): boolean {
  return document.cookie.split('; ').some((entry) => entry.startsWith(`${LOCALE_COOKIE}=`))
}
