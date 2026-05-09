'use client'

import { useState, useEffect } from 'react'
import { useSearchParams } from 'next/navigation'
import toast from 'react-hot-toast'
import { Loader2, User, CreditCard, TrendingUp, ExternalLink, CheckCircle } from 'lucide-react'
import { apiClient } from '@/lib/api/client'

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
        <Loader2 className="h-8 w-8 animate-spin text-primary-500" />
      </div>
    )
  }

  const tabs: { id: Tab; label: string; icon: any }[] = [
    { id: 'profile', label: 'Profile', icon: User },
    { id: 'payouts', label: 'Payouts', icon: CreditCard },
    { id: 'earnings', label: 'Earnings', icon: TrendingUp },
  ]

  return (
    <div className="container mx-auto px-4 py-8 max-w-3xl">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">Creator Studio</h1>
        <p className="text-sm text-gray-500 mt-1">Manage your creator profile, payouts, and earnings</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-8 border-b border-gray-200">
        {tabs.map(t => {
          const Icon = t.icon
          return (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors ${
                tab === t.id
                  ? 'border-primary-500 text-primary-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              <Icon className="h-4 w-4" />
              {t.label}
            </button>
          )
        })}
      </div>

      {/* Profile tab */}
      {tab === 'profile' && (
        <div className="space-y-6">
          <div className="rounded-lg border border-gray-200 bg-white p-6">
            <h2 className="font-semibold text-gray-900 mb-4">Public Profile</h2>
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Username</label>
                  <input
                    type="text"
                    value={profile.username || ''}
                    onChange={e => updateProfile({ username: e.target.value })}
                    placeholder="your-username"
                    className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:border-primary-500 focus:outline-none"
                  />
                  <p className="text-xs text-gray-400 mt-1">/creators/{profile.username || 'username'}</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Display Name</label>
                  <input
                    type="text"
                    value={profile.display_name || ''}
                    onChange={e => updateProfile({ display_name: e.target.value })}
                    placeholder="Your Name"
                    className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:border-primary-500 focus:outline-none"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Bio</label>
                <textarea
                  value={profile.bio || ''}
                  onChange={e => updateProfile({ bio: e.target.value })}
                  placeholder="Tell people about yourself and the agents you build"
                  rows={3}
                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:border-primary-500 focus:outline-none resize-none"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Avatar URL</label>
                <input
                  type="url"
                  value={profile.avatar_url || ''}
                  onChange={e => updateProfile({ avatar_url: e.target.value })}
                  placeholder="https://..."
                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:border-primary-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Banner Image URL</label>
                <input
                  type="url"
                  value={profile.banner_image_url || ''}
                  onChange={e => updateProfile({ banner_image_url: e.target.value })}
                  placeholder="https://..."
                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:border-primary-500 focus:outline-none"
                />
              </div>
            </div>
          </div>

          <div className="rounded-lg border border-gray-200 bg-white p-6">
            <h2 className="font-semibold text-gray-900 mb-4">Social Links</h2>
            <div className="space-y-3">
              {(['website_url', 'twitter_url', 'linkedin_url', 'github_url'] as const).map(field => (
                <div key={field}>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    {field === 'website_url' ? 'Website' : field === 'twitter_url' ? 'Twitter' : field === 'linkedin_url' ? 'LinkedIn' : 'GitHub'}
                  </label>
                  <input
                    type="url"
                    value={profile[field] || ''}
                    onChange={e => updateProfile({ [field]: e.target.value })}
                    placeholder="https://..."
                    className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:border-primary-500 focus:outline-none"
                  />
                </div>
              ))}
            </div>
          </div>

          <div className="flex justify-end">
            <button
              onClick={handleSave}
              disabled={saving}
              className="inline-flex items-center gap-2 px-6 py-2.5 bg-primary-600 hover:bg-primary-700 text-white rounded-lg text-sm font-medium transition-colors"
            >
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              Save profile
            </button>
          </div>
        </div>
      )}

      {/* Payouts tab */}
      {tab === 'payouts' && (
        <div className="space-y-6">
          <div className="rounded-lg border border-gray-200 bg-white p-6">
            <h2 className="font-semibold text-gray-900 mb-2">Stripe Connect</h2>
            <p className="text-sm text-gray-500 mb-6">
              Connect your Stripe account to receive payouts for agent subscriptions. Payouts are processed on the 1st of each month.
            </p>
            {profile.stripe_onboarding_complete ? (
              <div className="flex items-center gap-3 p-4 bg-primary-50 rounded-lg border border-primary-200">
                <CheckCircle className="h-5 w-5 text-primary-600 flex-shrink-0" />
                <div>
                  <div className="font-medium text-primary-800 text-sm">Stripe account connected</div>
                  <div className="text-xs text-primary-600 mt-0.5">Account ID: {profile.stripe_account_id}</div>
                </div>
              </div>
            ) : (
              <button
                onClick={handleStripeOnboard}
                className="inline-flex items-center gap-2 px-6 py-2.5 bg-[#635bff] hover:bg-[#5a52ee] text-white rounded-lg text-sm font-medium transition-colors"
              >
                <ExternalLink className="h-4 w-4" />
                Connect with Stripe
              </button>
            )}
          </div>

          {payouts.length > 0 && (
            <div className="rounded-lg border border-gray-200 bg-white overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-200">
                <h2 className="font-semibold text-gray-900">Payout History</h2>
              </div>
              <div className="divide-y divide-gray-100">
                {payouts.map((p: any) => (
                  <div key={p.id} className="px-6 py-4 flex items-center justify-between">
                    <div>
                      <div className="text-sm font-medium text-gray-900">{p.creator_credits} credits</div>
                      <div className="text-xs text-gray-400">{new Date(p.created_at).toLocaleDateString()}</div>
                    </div>
                    <span className="px-2 py-1 bg-primary-50 text-primary-700 rounded text-xs font-medium">
                      Paid
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Earnings tab */}
      {tab === 'earnings' && (
        <div>
          {earnings ? (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
              {[
                { label: 'Total Earned', value: earnings.total_credits || 0, unit: 'credits' },
                { label: 'This Month', value: earnings.current_month_credits || 0, unit: 'credits' },
                { label: 'Pending Payout', value: earnings.pending_credits || 0, unit: 'credits' },
              ].map(stat => (
                <div key={stat.label} className="rounded-lg border border-gray-200 bg-white p-6">
                  <div className="text-sm text-gray-500 mb-1">{stat.label}</div>
                  <div className="text-2xl font-bold text-gray-900">{stat.value.toLocaleString()}</div>
                  <div className="text-xs text-gray-400">{stat.unit}</div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-16 text-gray-400">
              <TrendingUp className="h-12 w-12 mx-auto mb-4 opacity-20" />
              <p>No earnings data yet</p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
