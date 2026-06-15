'use client'

import { useCallback, useEffect, useState } from 'react'
import { extractErrorMessage } from '@/lib/api/error'
import { CheckCircle, XCircle, Clock, MessageSquare, RefreshCw } from 'lucide-react'

interface ApprovalRequest {
  id: string
  task_id: string
  agent_name: string
  tool_name: string
  tool_args: Record<string, unknown>
  status: string
  notification_channel: string
  expires_at: string
  created_at: string
}

interface Props {
  agentName: string
  onCountChange?: (count: number) => void
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const secs = Math.floor(diff / 1000)
  if (secs < 60) return `${secs}s ago`
  const mins = Math.floor(secs / 60)
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  return `${hrs}h ago`
}

function timeUntil(iso: string): string {
  const diff = new Date(iso).getTime() - Date.now()
  if (diff <= 0) return 'expired'
  const mins = Math.floor(diff / 60000)
  if (mins < 60) return `${mins}m left`
  return `${Math.floor(mins / 60)}h left`
}

function ApprovalCard({
  approval,
  agentSlug,
  onResponded,
}: {
  approval: ApprovalRequest
  agentSlug: string
  onResponded: () => void
}) {
  const [responding, setResponding] = useState(false)
  const [showFeedback, setShowFeedback] = useState(false)
  const [feedback, setFeedback] = useState('')
  const [error, setError] = useState<string | null>(null)

  const expired = new Date(approval.expires_at).getTime() < Date.now()

  async function respond(decision: 'approved' | 'rejected' | 'feedback') {
    setResponding(true)
    setError(null)
    try {
      const { apiClient } = await import('@/lib/api/client')
      await apiClient.request(
        'POST',
        `/api/v1/agents/${encodeURIComponent(agentSlug)}/autonomous/approvals/${approval.id}/respond`,
        {
          decision,
          feedback_text: decision === 'feedback' ? feedback : undefined,
        }
      )
      onResponded()
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } }; message?: string }
      setError(extractErrorMessage(e, 'Request failed'))
    } finally {
      setResponding(false)
    }
  }

  return (
    <div className={`rounded-lg border ${expired ? 'border-gray-200 opacity-60' : 'border-amber-200 bg-amber-50'} p-4`}>
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <Clock className="w-4 h-4 text-amber-500 flex-shrink-0" />
            <span className="text-xs font-medium text-amber-700">Pending Action</span>
            <span className="text-xs text-gray-400 ml-auto">{timeAgo(approval.created_at)}</span>
          </div>

          <div className="mb-2">
            <span className="text-xs text-gray-500">Tool: </span>
            <code className="text-xs font-mono bg-white border border-gray-200 rounded px-1.5 py-0.5 text-gray-800">
              {approval.tool_name}
            </code>
            <span className="ml-2 text-xs text-gray-400">via {approval.notification_channel}</span>
          </div>

          <pre className="text-xs bg-white border border-gray-200 rounded p-2 overflow-auto max-h-32 text-gray-700 whitespace-pre-wrap">
            {JSON.stringify(approval.tool_args, null, 2)}
          </pre>

          <div className="mt-1 text-xs text-gray-400">{expired ? 'Expired' : timeUntil(approval.expires_at)}</div>
        </div>
      </div>

      {error && (
        <div className="mt-2 text-xs text-red-600 bg-red-50 border border-red-200 rounded px-2 py-1">
          {error}
        </div>
      )}

      {!expired && (
        <div className="mt-3 space-y-2">
          {showFeedback ? (
            <div className="space-y-2">
              <textarea
                rows={2}
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-500"
                placeholder="Describe the changes you want..."
                value={feedback}
                onChange={e => setFeedback(e.target.value)}
              />
              <div className="flex gap-2">
                <button
                  onClick={() => respond('feedback')}
                  disabled={responding || !feedback.trim()}
                  className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md text-xs font-medium text-white bg-blue-500 hover:bg-blue-600 disabled:opacity-50"
                >
                  <MessageSquare className="w-3 h-3" />
                  {responding ? 'Sending…' : 'Send Feedback'}
                </button>
                <button
                  onClick={() => setShowFeedback(false)}
                  className="px-3 py-1.5 rounded-md text-xs text-gray-600 border border-gray-300 hover:bg-gray-50"
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <div className="flex flex-wrap gap-2">
              <button
                onClick={() => respond('approved')}
                disabled={responding}
                className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md text-xs font-medium text-white bg-green-600 hover:bg-green-700 disabled:opacity-50"
              >
                <CheckCircle className="w-3 h-3" />
                {responding ? 'Processing…' : 'Approve'}
              </button>
              <button
                onClick={() => respond('rejected')}
                disabled={responding}
                className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md text-xs font-medium text-white bg-red-500 hover:bg-red-600 disabled:opacity-50"
              >
                <XCircle className="w-3 h-3" />
                Reject
              </button>
              <button
                onClick={() => setShowFeedback(true)}
                disabled={responding}
                className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md text-xs font-medium text-gray-700 border border-gray-300 hover:bg-gray-50 disabled:opacity-50"
              >
                <MessageSquare className="w-3 h-3" />
                Feedback…
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export function AutonomousApprovals({ agentName, onCountChange }: Props) {
  const [approvals, setApprovals] = useState<ApprovalRequest[]>([])
  const [loading, setLoading] = useState(true)

  const fetchApprovals = useCallback(async () => {
    try {
      const { apiClient } = await import('@/lib/api/client')
      const data = await apiClient.request(
        'GET',
        `/api/v1/agents/${encodeURIComponent(agentName)}/autonomous/approvals`
      )
      const list = Array.isArray(data) ? data : []
      setApprovals(list)
      onCountChange?.(list.filter((a: ApprovalRequest) => a.status === 'pending').length)
    } catch {
      setApprovals([])
    } finally {
      setLoading(false)
    }
  }, [agentName, onCountChange])

  useEffect(() => {
    fetchApprovals()
    const interval = setInterval(fetchApprovals, 10_000)
    return () => clearInterval(interval)
  }, [fetchApprovals])

  if (loading) {
    return (
      <div className="flex items-center justify-center py-10">
        <div className="w-5 h-5 border-2 border-red-500 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-600">
          {approvals.length === 0
            ? 'No pending approvals.'
            : `${approvals.length} action${approvals.length > 1 ? 's' : ''} waiting for your review.`}
        </p>
        <button
          onClick={fetchApprovals}
          className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700"
        >
          <RefreshCw className="w-3 h-3" />
          Refresh
        </button>
      </div>

      {approvals.length === 0 ? (
        <div className="py-8 text-center text-sm text-gray-400 border border-dashed border-gray-200 rounded-lg">
          When the agent proposes an action that requires approval, it will appear here.
        </div>
      ) : (
        <div className="space-y-3">
          {approvals.map(a => (
            <ApprovalCard key={a.id} approval={a} agentSlug={agentName} onResponded={fetchApprovals} />
          ))}
        </div>
      )}
    </div>
  )
}
