'use client'

import { useEffect, useRef, useState } from 'react'
import { useAuthStore } from '@/lib/store/authStore'
import { useRouter } from 'next/navigation'
import { useSubscription, useCredits } from '@/hooks/useBilling'
import { useTranslations } from 'next-intl'
import { LanguageSwitcher } from '@/components/i18n/LanguageSwitcher'

interface HeaderProps {
  onMobileMenuToggle?: () => void
}

export function Header({ onMobileMenuToggle }: HeaderProps) {
  const t = useTranslations('layout.header')
  const user = useAuthStore((state) => state.user)
  const signOut = useAuthStore((state) => state.signOut)
  const router = useRouter()
  const { subscription, loading: subscriptionLoading } = useSubscription()
  const { balance, loading: balanceLoading } = useCredits()
  const [menuOpen, setMenuOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  // Close the user menu on a click outside it or on Escape
  useEffect(() => {
    if (!menuOpen) return
    const onPointerDown = (event: PointerEvent) => {
      if (!menuRef.current?.contains(event.target as Node)) setMenuOpen(false)
    }
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setMenuOpen(false)
    }
    document.addEventListener('pointerdown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('pointerdown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [menuOpen])

  const handleSignOut = async () => {
    setMenuOpen(false)
    await signOut()
    router.push('/signin')
  }

  const handleUpgradeClick = () => {
    router.push('/billing')
  }

  // Calculate credit display
  const usedCredits = balance?.used_credits || 0
  const totalCredits = balance?.total_credits || 0

  // Determine subscription status
  const subscriptionName = subscription?.plan_name || 'Free'
  const hasSubscription = subscription !== null
  
  // Combined loading state
  const loading = subscriptionLoading || balanceLoading

  return (
    <header className="dashboard-app sticky top-0 z-30 flex h-16 items-center justify-between border-b border-black/10 bg-paper/80 px-4 md:px-6">
      {/* Hamburger — mobile only */}
      <button
        className="rounded-xl border border-black/10 bg-white/60 p-2 text-ink-soft transition-colors hover:bg-white md:hidden"
        onClick={onMobileMenuToggle}
        aria-label={t('openMenu')}
      >
        <svg aria-hidden="true" className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
        </svg>
      </button>

      <div className="flex items-center gap-2 md:gap-4 ml-auto">
        <LanguageSwitcher />

        {/* Credits Badge */}
        <div className="flex cursor-pointer items-center gap-1.5 rounded-full border border-black/10 bg-white/70 px-3 py-2 transition-colors hover:bg-white" onClick={() => router.push('/billing')}>
          <div className={`h-2 w-2 flex-shrink-0 rounded-full ${hasSubscription ? 'bg-leaf' : 'bg-ash'}`}></div>
          <span className="hidden sm:inline text-sm text-ink-soft">{subscriptionName}</span>
          {loading ? (
            <span className="text-sm font-semibold text-ink min-w-[50px] inline-block">&nbsp;</span>
          ) : (
            <span className="text-sm font-semibold text-ink">
              {usedCredits}/{totalCredits}
            </span>
          )}
        </div>

        {/* Upgrade Button - Only show if no subscription */}
        {!hasSubscription && (
          <button
            onClick={handleUpgradeClick}
            className="hidden rounded-full bg-ink px-4 py-2 text-sm font-medium text-paper transition-transform motion-reduce:transition-none hover:-translate-y-0.5 sm:inline-flex"
          >
            {t('upgrade')}
          </button>
        )}

        {/* User Menu */}
        <div className="relative" ref={menuRef}>
          <button
            type="button"
            aria-haspopup="menu"
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen((open) => !open)}
            className="flex items-center gap-2 rounded-full border border-black/10 bg-white/70 px-3 py-2 transition-colors hover:bg-white"
          >
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-ink text-sm font-semibold text-white">
              {user?.name?.charAt(0).toUpperCase() || 'U'}
            </div>
            <span className="text-sm font-medium text-ink-soft">{user?.name || t('defaultUser')}</span>
            <svg aria-hidden="true" className="w-4 h-4 text-ash" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>

          {/* Dropdown Menu: opens on click, so it works with a mouse, touch and the keyboard */}
          {menuOpen && (
            <div role="menu" className="dashboard-surface absolute right-0 top-full z-40 mt-2 w-48 rounded-2xl">
              <div className="py-1">
                <button
                  type="button"
                  role="menuitem"
                  onClick={handleSignOut}
                  className="w-full rounded-2xl px-4 py-2 text-left text-sm text-ink-soft transition-colors hover:bg-black/5"
                >
                  {t('signOut')}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}
