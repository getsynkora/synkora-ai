'use client'

import type { ReactNode } from 'react'
import Link from 'next/link'
import { useTranslations } from 'next-intl'
import { LanguageSwitcher } from '@/components/i18n/LanguageSwitcher'

export default function AuthPageFrame({
  children,
}: {
  children: ReactNode
}) {
  const t = useTranslations('auth.frame')
  return (
    <div className="auth-page min-h-screen">
      <div className="mx-auto max-w-[1480px] px-6 py-6 lg:px-10">
        <div className="mb-8 flex items-center justify-between">
          <Link href="/" className="inline-flex flex-col">
            <div className="flex items-center gap-3">
              <span className="whitespace-nowrap text-[2rem] font-semibold leading-none tracking-[0.18em] text-ink">
                SYNKORA
              </span>
            </div>
            <span className="mt-2 whitespace-nowrap text-xs text-ink-mute">
              {t('tagline')}
            </span>
          </Link>
          <div className="flex items-center gap-4">
            <LanguageSwitcher />
            <Link href="/signin" className="hidden text-sm font-medium sm:inline text-ink-soft transition-colors hover:text-black">
              {t('signIn')}
            </Link>
            <Link
              href="/signup"
              className="hidden rounded-[1.75rem] bg-ink px-5 py-3 text-sm font-semibold text-paper transition-colors hover:bg-ink/85 sm:inline-flex"
            >
              {t('getStarted')}
            </Link>
          </div>
        </div>
        {children}
      </div>
    </div>
  )
}
