'use client'

import { useState, useEffect } from 'react'
import { useSearchParams } from 'next/navigation'
import toast from 'react-hot-toast'
import { Loader2, User, CreditCard, TrendingUp, ExternalLink, CheckCircle } from 'lucide-react'
import { apiClient } from '@/lib/api/client'
import DashboardPageShell, { DashboardPagePanel, DashboardPageTabs } from '@/components/dashboard/DashboardPageShell'

type Tab = 'profile' | 'payouts' | 'earnings'

interface CreatorProfile {
  username?: string
  display_name?: string
  bio?: string
  avatar_url?: string
  banner_image_url?: string
  website_url?: string
  twitter_url?: string
  linkedin_url?: string
  github_url?: string
  stripe_account_id?: string
  stripe_onboarding_complete?: boolean
  total_earnings_credits?: number
}

export default function CreatorProfilePage() {
  const searchParams = useSearchParams()
  const initialTab = (searchParams.get('tab') as Tab) || 'profile'
  const [tab, setTab] = useState<Tab>(initialTab)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [profile, setProfile] = useState<CreatorProfile>({})
  const [earnings, setEarnings] = useState<any>(null)
  const [payouts, setPayouts] = useState<any[]>([])

  useEffect(() => {
    async function loadData() {
      try {
        const [profileRes, earningsRes, payoutsRes] = await Promise.allSettled([
          apiClient.request('GET', '/api/v1/creator-profile'),
          apiClient.request('GET', '/api/v1/creator-profile/earnings'),
          apiClient.request('GET', '/api/v1/creator-profile/payouts'),
        ])
        if (profileRes.status === 'fulfilled') setProfile(profileRes.value?.profile || {})
        if (earningsRes.status === 'fulfilled') setEarnings(earningsRes.value?.earnings)
        if (payoutsRes.status === 'fulfilled') setPayouts(payoutsRes.value?.payouts || [])
      } catch {
        // ignore
      } finally {
        setLoading(false)
      }
    }
    loadData()
  }, [])

  const handleSave = async () => {
    setSaving(true)
    try {
      await apiClient.request('PUT', '/api/v1/creator-profile', profile)
      toast.success('Profile saved')
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  const handleStripeOnboard = async () => {
    try {
      const res = await apiClient.request('POST', '/api/v1/creator-profile/stripe-onboard', {
        refresh_url: window.location.href,
        return_url: window.location.href + '?stripe=complete',
      })
      window.location.href = res?.onboarding_url
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'Stripe onboarding failed')
    }
  }

  const updateProfile = (updates: Partial<CreatorProfile>) => setProfile(prev => ({ ...prev, ...updates }))

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 motion-safe:animate-spin text-primary-500" />
      </div>
    )
  }

  const tabs: { id: Tab; label: string; icon: any }[] = [
    { id: 'profile', label: 'Profile', icon: User },
    { id: 'payouts', label: 'Payouts', icon: CreditCard },
    { id: 'earnings', label: 'Earnings', icon: TrendingUp },
  ]

  const fieldClass =
    'w-full rounded-[1.1rem] border border-black/10 bg-cream px-4 py-3 text-sm text-ink placeholder-ash transition-[color,background-color,border-color,box-shadow,opacity,transform] focus:border-transparent focus:outline-none focus:ring-2 focus:ring-mint'
  const sectionTitleClass = 'text-lg font-semibold tracking-[-0.02em] text-ink'

  return (
    <DashboardPageShell
      title="Creator Studio"
      description="Manage your creator profile, payouts, and earnings."
      icon={User}
      badge="Settings"
      backHref="/settings/profile"
      backLabel="Back to Settings"
      maxWidthClassName="max-w-5xl"
      breadcrumbs={[
        { label: 'Home', href: '/' },
        { label: 'Settings', href: '/settings/profile' },
        { label: 'Creator Studio' },
      ]}
      actions={
        tab === 'profile' ? (
          <button
            onClick={handleSave}
            disabled={saving}
            className="inline-flex items-center gap-2 rounded-[1rem] bg-ink px-4 py-3 text-sm font-semibold text-white transition-colors hover:bg-black disabled:opacity-50"
          >
            {saving ? <Loader2 className="h-4 w-4 motion-safe:animate-spin" /> : null}
            Save profile
          </button>
        ) : null
      }
    >
      <div className="space-y-6">
        <DashboardPageTabs
          activeId={tab}
          onChange={(value) => setTab(value as Tab)}
          items={tabs.map((t) => ({
            id: t.id,
            label: t.label,
            icon: <t.icon className="h-4 w-4" />,
          }))}
        />

        {tab === 'profile' && (
          <div className="space-y-6">
            <DashboardPagePanel className="p-6 sm:p-7">
              <h2 className={sectionTitleClass}>Public Profile</h2>
              <div className="mt-5 space-y-4">
                <div className="grid gap-4 md:grid-cols-2">
                  <div>
                    <label className="mb-1.5 block text-sm font-semibold text-ink-soft">Username</label>
                    <input
                      type="text"
                      value={profile.username || ''}
                      onChange={e => updateProfile({ username: e.target.value })}
                      placeholder="your-username"
                      className={fieldClass}
                    />
                    <p className="mt-1.5 text-xs text-ash">/creators/{profile.username || 'username'}</p>
                  </div>
                  <div>
                    <label className="mb-1.5 block text-sm font-semibold text-ink-soft">Display Name</label>
                    <input
                      type="text"
                      value={profile.display_name || ''}
                      onChange={e => updateProfile({ display_name: e.target.value })}
                      placeholder="Your Name"
                      className={fieldClass}
                    />
                  </div>
                </div>

                <div>
                  <label className="mb-1.5 block text-sm font-semibold text-ink-soft">Bio</label>
                  <textarea
                    value={profile.bio || ''}
                    onChange={e => updateProfile({ bio: e.target.value })}
                    placeholder="Tell people about yourself and the agents you build"
                    rows={4}
                    className={`${fieldClass} resize-none`}
                  />
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                  <div>
                    <label className="mb-1.5 block text-sm font-semibold text-ink-soft">Avatar URL</label>
                    <input
                      type="url"
                      value={profile.avatar_url || ''}
                      onChange={e => updateProfile({ avatar_url: e.target.value })}
                      placeholder="https://..."
                      className={fieldClass}
                    />
                  </div>
                  <div>
                    <label className="mb-1.5 block text-sm font-semibold text-ink-soft">Banner Image URL</label>
                    <input
                      type="url"
                      value={profile.banner_image_url || ''}
                      onChange={e => updateProfile({ banner_image_url: e.target.value })}
                      placeholder="https://..."
                      className={fieldClass}
                    />
                  </div>
                </div>
              </div>
            </DashboardPagePanel>

            <DashboardPagePanel className="p-6 sm:p-7">
              <h2 className={sectionTitleClass}>Social Links</h2>
              <div className="mt-5 grid gap-4 md:grid-cols-2">
                {(['website_url', 'twitter_url', 'linkedin_url', 'github_url'] as const).map((field) => (
                  <div key={field}>
                    <label className="mb-1.5 block text-sm font-semibold text-ink-soft">
                      {field === 'website_url' ? 'Website' : field === 'twitter_url' ? 'Twitter' : field === 'linkedin_url' ? 'LinkedIn' : 'GitHub'}
                    </label>
                    <input
                      type="url"
                      value={profile[field] || ''}
                      onChange={e => updateProfile({ [field]: e.target.value })}
                      placeholder="https://..."
                      className={fieldClass}
                    />
                  </div>
                ))}
              </div>
            </DashboardPagePanel>
          </div>
        )}

        {tab === 'payouts' && (
          <div className="space-y-6">
            <DashboardPagePanel className="p-6 sm:p-7">
              <h2 className={sectionTitleClass}>Stripe Connect</h2>
              <p className="mt-2 text-sm leading-6 text-ink-soft">
                Connect your Stripe account to receive payouts for agent subscriptions. Payouts are processed on the 1st of each month.
              </p>
              {profile.stripe_onboarding_complete ? (
                <div className="mt-5 flex items-center gap-3 rounded-[1.2rem] border border-leaf-wash bg-leaf-wash p-4">
                  <CheckCircle className="h-5 w-5 flex-shrink-0 text-forest" />
                  <div>
                    <div className="text-sm font-semibold text-forest">Stripe account connected</div>
                    <div className="mt-0.5 text-xs text-forest">Account ID: {profile.stripe_account_id}</div>
                  </div>
                </div>
              ) : (
                <button
                  onClick={handleStripeOnboard}
                  className="mt-5 inline-flex items-center gap-2 rounded-[1rem] bg-ink px-4 py-3 text-sm font-semibold text-white transition-colors hover:bg-black"
                >
                  <ExternalLink className="h-4 w-4" />
                  Connect with Stripe
                </button>
              )}
            </DashboardPagePanel>

            {payouts.length > 0 ? (
              <DashboardPagePanel className="overflow-hidden">
                <div className="border-b border-sand-deep px-6 py-4">
                  <h2 className={sectionTitleClass}>Payout History</h2>
                </div>
                <div className="divide-y divide-sand-deep">
                  {payouts.map((p: any) => (
                    <div key={p.id} className="flex items-center justify-between gap-4 px-6 py-4">
                      <div>
                        <div className="text-sm font-semibold text-ink">{p.creator_credits} credits</div>
                        <div className="text-xs text-ash">{new Date(p.created_at).toLocaleDateString()}</div>
                      </div>
                      <span className="rounded-full bg-sand px-3 py-1 text-xs font-semibold text-ink">Paid</span>
                    </div>
                  ))}
                </div>
              </DashboardPagePanel>
            ) : null}
          </div>
        )}

        {tab === 'earnings' && (
          <div>
            {earnings ? (
              <div className="grid gap-4 md:grid-cols-3">
                {[
                  { label: 'Total Earned', value: earnings.total_credits || 0, unit: 'credits' },
                  { label: 'This Month', value: earnings.current_month_credits || 0, unit: 'credits' },
                  { label: 'Pending Payout', value: earnings.pending_credits || 0, unit: 'credits' },
                ].map((stat) => (
                  <DashboardPagePanel key={stat.label} className="p-6">
                    <div className="text-sm text-ink-mute">{stat.label}</div>
                    <div className="mt-2 text-3xl font-semibold tracking-[-0.04em] text-ink">
                      {stat.value.toLocaleString()}
                    </div>
                    <div className="mt-1 text-xs text-clay">{stat.unit}</div>
                  </DashboardPagePanel>
                ))}
              </div>
            ) : (
              <DashboardPagePanel className="p-12 text-center">
                <TrendingUp className="mx-auto mb-4 h-12 w-12 text-taupe" />
                <p className="text-sm text-ink-mute">No earnings data yet.</p>
              </DashboardPagePanel>
            )}
          </div>
        )}
      </div>
    </DashboardPageShell>
  )
}
