'use client'

import { useLocale, useTranslations } from 'next-intl'
import { useRouter } from 'next/navigation'
import { locales, localeNames, normalizeLocale, type Locale } from '@/i18n/config'
import { saveLocaleCookie } from '@/lib/i18n/client'
import { apiClient } from '@/lib/api/client'
import { useAuthStore } from '@/lib/store/authStore'

/** Picks the language of the dashboard; remembered in this browser and, when signed in, on the account. */
export function LanguageSwitcher({ className = '' }: { className?: string }) {
  const locale = useLocale()
  const t = useTranslations('common.language')
  const router = useRouter()
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)

  async function change(value: string) {
    const next = normalizeLocale(value)
    if (!next || next === locale) return
    saveLocaleCookie(next)
    router.refresh()
    if (isAuthenticated) {
      try {
        await apiClient.request('PUT', '/api/v1/profile/me', { interface_language: next })
      } catch {
        // The choice still applies in this browser; it will be saved with the next change.
      }
    }
  }

  return (
    <label className={className}>
      <span className="sr-only">{t('label')}</span>
      <select
        value={normalizeLocale(locale) ?? 'en'}
        onChange={(event) => change(event.target.value)}
        className="rounded-xl border border-black/10 bg-white/80 px-3 py-2 text-sm text-gray-700 shadow-sm focus:outline-none focus:ring-2 focus:ring-[#79dfbc]"
      >
        {locales.map((code: Locale) => (
          <option key={code} value={code}>
            {localeNames[code]}
          </option>
        ))}
      </select>
    </label>
  )
}
