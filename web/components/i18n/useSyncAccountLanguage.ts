'use client'

import { useEffect } from 'react'
import { useLocale } from 'next-intl'
import { useRouter } from 'next/navigation'
import { normalizeLocale } from '@/i18n/config'
import { hasLocaleCookie, saveLocaleCookie } from '@/lib/i18n/client'

/**
 * Applies the language saved on the account to a browser that has not picked one
 * yet (a new device or browser). A language chosen in this browser always wins.
 */
export function useSyncAccountLanguage(accountLanguage: string | undefined) {
  const locale = useLocale()
  const router = useRouter()

  useEffect(() => {
    const saved = normalizeLocale(accountLanguage)
    if (!saved || saved === locale || hasLocaleCookie()) return
    saveLocaleCookie(saved)
    router.refresh()
  }, [accountLanguage, locale, router])
}
