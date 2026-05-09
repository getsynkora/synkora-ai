'use client'

import { useState, useEffect, useCallback } from 'react'
import Link from 'next/link'
import toast from 'react-hot-toast'
import { Loader2, Zap, Clock, XCircle, ExternalLink } from 'lucide-react'
import { apiClient } from '@/lib/api/client'

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
      <div className={`rounded-lg border bg-white p-5 ${isActive ? 'border-gray-200' : 'border-gray-100 opacity-60'}`}>
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className="font-semibold text-gray-900 truncate">
                {sub.agent_name || `Agent ${sub.agent_id.slice(0, 8)}…`}
              </span>
              <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                sub.status === 'ACTIVE' ? 'bg-emerald-100 text-emerald-700' :
                sub.status === 'EXPIRED' ? 'bg-red-100 text-red-600' :
                'bg-gray-100 text-gray-600'
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
                className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
                title="View agent page"
              >
                <ExternalLink className="h-4 w-4" />
              </Link>
            )}
            {isActive && (
              <button
                onClick={() => handleCancel(sub.id)}
                disabled={cancelling === sub.id}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm text-red-600 hover:bg-red-50 rounded-lg border border-red-200 transition-colors disabled:opacity-50"
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
      </div>
    )
  }

  return (
    <div className="container mx-auto px-4 py-8 max-w-3xl">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">My Agent Subscriptions</h1>
        <p className="text-sm text-gray-500 mt-1">Agents you have paid to access</p>
      </div>

      {loading ? (
        <div className="flex justify-center py-16">
          <Loader2 className="h-8 w-8 animate-spin text-emerald-500" />
        </div>
      ) : subs.length === 0 ? (
        <div className="text-center py-16 text-gray-400">
          <Zap className="h-12 w-12 mx-auto mb-4 opacity-20" />
          <p className="font-medium">No subscriptions yet</p>
          <p className="text-sm mt-1">Subscribe to paid agents to see them here</p>
        </div>
      ) : (
        <div className="space-y-8">
          {active.length > 0 && (
            <div>
              <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">Active ({active.length})</h2>
              <div className="space-y-3">
                {active.map(sub => <SubCard key={sub.id} sub={sub} />)}
              </div>
            </div>
          )}
          {past.length > 0 && (
            <div>
              <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">Past ({past.length})</h2>
              <div className="space-y-3">
                {past.map(sub => <SubCard key={sub.id} sub={sub} />)}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
