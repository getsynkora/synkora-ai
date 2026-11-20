'use client'

import { useState, useEffect, useCallback } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import { ArrowLeft, Loader2, Users, Clock, CheckCircle, XCircle } from 'lucide-react'
import { apiClient } from '@/lib/api/client'

interface Subscriber {
  id: string
  subscriber_tenant_id: string | null
  guest_email: string | null
  pricing_tier: string
  amount_cents: number
  status: 'ACTIVE' | 'CANCELLED' | 'EXPIRED'
  started_at: string
  expires_at: string | null
  cancelled_at: string | null
}

const TIER_LABELS: Record<string, string> = {
  SESSION: 'Session',
  DAILY: 'Daily',
  WEEKLY: 'Weekly',
  MONTHLY: 'Monthly',
  EMAIL_ONE_TIME: 'Email (one-time)',
  EMAIL_MONTHLY: 'Email (monthly)',
}

const STATUS_STYLES: Record<string, string> = {
  ACTIVE: 'bg-primary-100 text-primary-700',
  CANCELLED: 'bg-sand text-ink-soft',
  EXPIRED: 'bg-blush-wash text-danger',
}

export default function SubscribersPage() {
  const { agentName } = useParams() as { agentName: string }
  const [subscribers, setSubscribers] = useState<Subscriber[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<'ALL' | 'ACTIVE' | 'EXPIRED' | 'CANCELLED'>('ALL')

  const load = useCallback(async () => {
    try {
      const res = await apiClient.request('GET', `/api/v1/agents/${agentName}/paid-subscribers`)
      setSubscribers(res?.subscribers || res || [])
    } catch {
      setSubscribers([])
    } finally {
      setLoading(false)
    }
  }, [agentName])

  useEffect(() => { load() }, [load])

  const filtered = filter === 'ALL' ? subscribers : subscribers.filter(s => s.status === filter)

  const stats = {
    active: subscribers.filter(s => s.status === 'ACTIVE').length,
    total: subscribers.length,
    revenue: subscribers.reduce((sum, s) => sum + (s.amount_cents || 0), 0),
  }

  return (
    <div className="container mx-auto px-4 py-8 max-w-4xl">
      <div className="mb-8">
        <Link
          href={`/agents/${agentName}/edit`}
          className="mb-2 inline-flex items-center text-sm text-ink-mute hover:text-ink-soft"
        >
          <ArrowLeft className="mr-1 h-4 w-4" /> Back
        </Link>
        <h1 className="text-2xl font-bold text-ink">Subscribers</h1>
        <p className="text-sm text-ink-mute mt-1">Users who have paid for access to this agent</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4 mb-8">
        {[
          { label: 'Active', value: stats.active, icon: CheckCircle, color: 'text-primary-600' },
          { label: 'Total', value: stats.total, icon: Users, color: 'text-azure' },
          { label: 'Revenue', value: `$${(stats.revenue / 100).toFixed(2)}`, icon: Clock, color: 'text-plum' },
        ].map(stat => {
          const Icon = stat.icon
          return (
            <div key={stat.label} className="rounded-lg border border-line bg-white p-4 flex items-center gap-3">
              <Icon className={`h-8 w-8 ${stat.color} opacity-70`} />
              <div>
                <div className="text-xl font-bold text-ink">{stat.value}</div>
                <div className="text-xs text-ink-mute">{stat.label}</div>
              </div>
            </div>
          )
        })}
      </div>

      {/* Filter */}
      <div className="flex gap-2 mb-6">
        {(['ALL', 'ACTIVE', 'EXPIRED', 'CANCELLED'] as const).map(f => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              filter === f ? 'bg-ink text-white' : 'bg-sand text-ink-soft hover:bg-line'
            }`}
          >
            {f === 'ALL' ? `All (${subscribers.length})` : `${f.charAt(0) + f.slice(1).toLowerCase()} (${subscribers.filter(s => s.status === f).length})`}
          </button>
        ))}
      </div>

      {/* List */}
      {loading ? (
        <div className="flex justify-center py-16">
          <Loader2 className="h-8 w-8 motion-safe:animate-spin text-primary-500" />
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-16 text-ash">
          <Users className="h-12 w-12 mx-auto mb-4 opacity-20" />
          <p className="font-medium">No subscribers yet</p>
          <p className="text-sm mt-1">Publish your landing page and set pricing to start earning</p>
          <Link
            href={`/agents/${agentName}/landing-page`}
            className="inline-flex items-center gap-1 mt-4 text-sm text-primary-600 hover:underline"
          >
            Go to landing page editor
          </Link>
        </div>
      ) : (
        <div className="rounded-lg border border-line bg-white overflow-hidden">
          <table className="min-w-full divide-y divide-line">
            <thead className="bg-cream">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-ink-mute">Subscriber</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-ink-mute">Tier</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-ink-mute">Status</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-ink-mute">Started</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-ink-mute">Expires</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-sand">
              {filtered.map(sub => (
                <tr key={sub.id} className="hover:bg-cream">
                  <td className="px-4 py-3">
                    <div className="text-sm text-ink">
                      {sub.guest_email || (sub.subscriber_tenant_id ? `Account ${sub.subscriber_tenant_id.slice(0, 8)}…` : 'Unknown')}
                    </div>
                    <div className="text-xs text-ash">{sub.guest_email ? 'Guest' : 'Account user'}</div>
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-sm text-ink-soft">{TIER_LABELS[sub.pricing_tier] || sub.pricing_tier}</span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${STATUS_STYLES[sub.status]}`}>
                      {sub.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-ink-soft whitespace-nowrap">
                    {new Date(sub.started_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3 text-sm text-ink-soft whitespace-nowrap">
                    {sub.expires_at ? new Date(sub.expires_at).toLocaleDateString() : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
