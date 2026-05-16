'use client'

import { useState, useEffect, useCallback } from 'react'
import Link from 'next/link'
import toast from 'react-hot-toast'
import { Loader2, Zap, Clock, XCircle, ExternalLink } from 'lucide-react'
import { apiClient } from '@/lib/api/client'
import DashboardPageShell, { DashboardPagePanel } from '@/components/dashboard/DashboardPageShell'

interface AgentSubscription {
  id: string
  agent_id: string
  agent_name?: string
  pricing_tier: string
  status: 'ACTIVE' | 'CANCELLED' | 'EXPIRED'
  started_at: string
  expires_at: string | null
  cancelled_at: string | null
  slug?: string
}

const TIER_LABELS: Record<string, string> = {
  SESSION: 'Session access',
  DAILY: '24-hour access',
  WEEKLY: '7-day access',
  MONTHLY: '30-day access',
  EMAIL_ONE_TIME: 'Email (one-time)',
  EMAIL_MONTHLY: 'Email subscription',
}

export default function MyAgentSubscriptionsPage() {
  const [subs, setSubs] = useState<AgentSubscription[]>([])
  const [loading, setLoading] = useState(true)
  const [cancelling, setCancelling] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const res = await apiClient.request('GET', '/api/v1/my/agent-subscriptions')
      setSubs(res?.subscriptions || res || [])
    } catch {
      setSubs([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const handleCancel = async (subId: string) => {
    if (!confirm('Cancel this subscription? You will lose access immediately.')) return
    setCancelling(subId)
    try {
      await apiClient.request('DELETE', `/api/v1/my/agent-subscriptions/${subId}`)
      toast.success('Subscription cancelled')
      load()
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'Failed to cancel')
    } finally {
      setCancelling(null)
    }
  }

  const active = subs.filter(s => s.status === 'ACTIVE')
  const past = subs.filter(s => s.status !== 'ACTIVE')

  const SubCard = ({ sub }: { sub: AgentSubscription }) => {
    const isActive = sub.status === 'ACTIVE'
    const daysLeft = sub.expires_at
      ? Math.max(0, Math.ceil((new Date(sub.expires_at).getTime() - Date.now()) / 86400000))
      : null

    return (
      <DashboardPagePanel className={`p-5 ${isActive ? '' : 'opacity-70'}`}>
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className="font-semibold text-gray-900 truncate">
                {sub.agent_name || `Agent ${sub.agent_id.slice(0, 8)}…`}
              </span>
              <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] ${
                sub.status === 'ACTIVE' ? 'bg-[#ebf5ee] text-[#24543b]' :
                sub.status === 'EXPIRED' ? 'bg-[#f8ecef] text-[#8a445c]' :
                'bg-[#f3ede5] text-[#6b5a4a]'
              }`}>
                {sub.status}
              </span>
            </div>

            <div className="text-sm text-gray-500">{TIER_LABELS[sub.pricing_tier] || sub.pricing_tier}</div>

            <div className="flex flex-wrap gap-4 mt-3 text-xs text-gray-400">
              <span className="flex items-center gap-1">
                <Clock className="h-3.5 w-3.5" />
                Started {new Date(sub.started_at).toLocaleDateString()}
              </span>
              {sub.expires_at && (
                <span className={`flex items-center gap-1 ${isActive && daysLeft !== null && daysLeft <= 2 ? 'text-red-500 font-medium' : ''}`}>
                  <Zap className="h-3.5 w-3.5" />
                  {isActive
                    ? daysLeft === 0 ? 'Expires today' : `${daysLeft}d left`
                    : `Expired ${new Date(sub.expires_at).toLocaleDateString()}`
                  }
                </span>
              )}
              {sub.cancelled_at && (
                <span>Cancelled {new Date(sub.cancelled_at).toLocaleDateString()}</span>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            {sub.slug && (
              <Link
                href={`/a/${sub.slug}`}
                target="_blank"
                className="rounded-[0.95rem] p-2 text-gray-400 transition-colors hover:bg-[#f3ecde] hover:text-[#171717]"
                title="View agent page"
              >
                <ExternalLink className="h-4 w-4" />
              </Link>
            )}
            {isActive && (
              <button
                onClick={() => handleCancel(sub.id)}
                disabled={cancelling === sub.id}
                className="inline-flex items-center gap-1.5 rounded-[0.95rem] border border-[#eed6dd] bg-[#fbf1f4] px-3 py-2 text-sm font-semibold text-[#8a445c] transition-colors hover:bg-[#f7e6ec] disabled:opacity-50"
              >
                {cancelling === sub.id
                  ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  : <XCircle className="h-3.5 w-3.5" />
                }
                Cancel
              </button>
            )}
          </div>
        </div>
      </DashboardPagePanel>
    )
  }

  return (
    <DashboardPageShell
      title="My Agent Subscriptions"
      description="Agents you have paid to access."
      icon={Zap}
      badge="Settings"
      backHref="/settings/profile"
      backLabel="Back to Settings"
      maxWidthClassName="max-w-5xl"
      breadcrumbs={[
        { label: 'Home', href: '/' },
        { label: 'Settings', href: '/settings/profile' },
        { label: 'My Agent Subscriptions' },
      ]}
      stats={[
        { label: 'Active', value: active.length },
        { label: 'Past', value: past.length },
      ]}
    >
      {loading ? (
        <div className="flex justify-center py-16">
          <Loader2 className="h-8 w-8 animate-spin text-[#171717]" />
        </div>
      ) : subs.length === 0 ? (
        <DashboardPagePanel className="p-12 text-center">
          <Zap className="mx-auto mb-4 h-12 w-12 text-gray-300" />
          <p className="font-semibold text-gray-900">No subscriptions yet</p>
          <p className="mt-1 text-sm text-gray-500">Subscribe to paid agents to see them here.</p>
        </DashboardPagePanel>
      ) : (
        <div className="space-y-8">
          {active.length > 0 ? (
            <div>
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-[0.2em] text-[#9a7a5e]">Active ({active.length})</h2>
              <div className="space-y-3">
                {active.map(sub => <SubCard key={sub.id} sub={sub} />)}
              </div>
            </div>
          ) : null}
          {past.length > 0 ? (
            <div>
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-[0.2em] text-[#9a7a5e]">Past ({past.length})</h2>
              <div className="space-y-3">
                {past.map(sub => <SubCard key={sub.id} sub={sub} />)}
              </div>
            </div>
          ) : null}
        </div>
      )}
    </DashboardPageShell>
  )
}
