'use client'

import { useAuthStore } from '@/lib/store/authStore'
import { useRouter } from 'next/navigation'
import { useSubscription, useCredits } from '@/hooks/useBilling'

interface HeaderProps {
  onMobileMenuToggle?: () => void
}

export function Header({ onMobileMenuToggle }: HeaderProps) {
  const user = useAuthStore((state) => state.user)
  const signOut = useAuthStore((state) => state.signOut)
  const router = useRouter()
  const { subscription, loading: subscriptionLoading } = useSubscription()
  const { balance, loading: balanceLoading } = useCredits()

  const handleSignOut = async () => {
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
    <header className="dashboard-app sticky top-0 z-30 flex h-16 items-center justify-between border-b border-black/10 bg-[rgba(247,242,231,0.82)] px-4 backdrop-blur-xl md:px-6">
      {/* Hamburger — mobile only */}
      <button
        className="rounded-xl border border-black/10 bg-white/60 p-2 text-gray-600 transition-colors hover:bg-white md:hidden"
        onClick={onMobileMenuToggle}
        aria-label="Open menu"
      >
        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
        </svg>
      </button>

      <div className="flex items-center gap-2 md:gap-4 ml-auto">
        {/* Credits Badge */}
        <div className="flex cursor-pointer items-center gap-1.5 rounded-full border border-black/10 bg-white/70 px-3 py-2 transition-colors hover:bg-white" onClick={() => router.push('/billing')}>
          <div className={`h-2 w-2 flex-shrink-0 rounded-full ${hasSubscription ? 'bg-[#2d8b69]' : 'bg-gray-400'}`}></div>
          <span className="hidden sm:inline text-sm text-gray-600">{subscriptionName}</span>
          {loading ? (
            <span className="text-sm font-semibold text-gray-900 min-w-[50px] inline-block">&nbsp;</span>
          ) : (
            <span className="text-sm font-semibold text-gray-900">
              {usedCredits}/{totalCredits}
            </span>
          )}
        </div>

        {/* Upgrade Button - Only show if no subscription */}
        {!hasSubscription && (
          <button
            onClick={handleUpgradeClick}
            className="hidden rounded-full bg-[#181818] px-4 py-2 text-sm font-medium text-[#f7f2e7] transition-transform hover:-translate-y-0.5 sm:inline-flex"
          >
            Upgrade
          </button>
        )}

        {/* User Menu */}
        <div className="relative group">
          <button className="flex items-center gap-2 rounded-full border border-black/10 bg-white/70 px-3 py-2 transition-colors hover:bg-white">
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[#181818] text-sm font-semibold text-white">
              {user?.name?.charAt(0).toUpperCase() || 'U'}
            </div>
            <span className="text-sm font-medium text-gray-700">{user?.name || 'User'}</span>
            <svg className="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>

          {/* Dropdown Menu */}
          <div className="dashboard-surface absolute right-0 mt-2 invisible w-48 rounded-2xl opacity-0 transition-all group-hover:visible group-hover:opacity-100">
            <div className="py-1">
              <button
                onClick={handleSignOut}
                className="w-full rounded-2xl px-4 py-2 text-left text-sm text-gray-700 transition-colors hover:bg-black/5"
              >
                Sign out
              </button>
            </div>
          </div>
        </div>
      </div>
    </header>
  )
}
