'use client'

import { useState, useEffect } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import { Phone, PhoneIncoming, Clock, ArrowLeft } from 'lucide-react'
import { getPhoneCalls, type PhoneCall } from '@/lib/api/phone'
import { apiClient } from '@/lib/api/client'
import AgentPageShell, { AgentPagePanel } from '@/components/agents/AgentPageShell'

const STATUS_BADGE: Record<string, { label: string; className: string }> = {
  completed: { label: 'Completed', className: 'bg-green-100 text-green-700' },
  active: { label: 'Active', className: 'bg-blue-100 text-blue-700' },
  ringing: { label: 'Ringing', className: 'bg-yellow-100 text-yellow-700' },
  failed: { label: 'Failed', className: 'bg-red-100 text-red-700' },
  no_answer: { label: 'No Answer', className: 'bg-gray-100 text-gray-600' },
}

function formatDuration(seconds: number | null): string {
  if (seconds == null) return '—'
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return m > 0 ? `${m}m ${s}s` : `${s}s`
}

function formatDate(iso: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString()
}

export default function AgentLensCallsPage() {
  const params = useParams()
  const agentName = params.agentName as string

  const [calls, setCalls] = useState<PhoneCall[]>([])
  const [loading, setLoading] = useState(true)
  const [agentId, setAgentId] = useState<string | null>(null)

  useEffect(() => {
    async function load() {
      try {
        const agent = await apiClient.getAgent(agentName)
        setAgentId(agent.id)
        const data = await getPhoneCalls({ agent_id: agent.id })
        setCalls(data)
      } catch {
        // no-op
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [agentName])

  return (
    <AgentPageShell agentName={agentName} title="Call History" icon={Phone}>
      <AgentPagePanel>
        <div className="space-y-4">
          {/* Header */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Phone className="w-4 h-4 text-gray-500" />
              <h2 className="text-base font-semibold text-gray-900">Call History</h2>
            </div>
            <Link
              href={`/agents/${agentName}/settings/phone`}
              className="text-sm text-gray-500 hover:text-gray-700 flex items-center gap-1"
            >
              Configure phone
            </Link>
          </div>

          {loading ? (
            <div className="flex items-center justify-center h-32 text-gray-400 text-sm">Loading…</div>
          ) : calls.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-40 text-gray-400 gap-2">
              <PhoneIncoming className="w-8 h-8 text-gray-300" />
              <p className="text-sm">No calls yet</p>
              <p className="text-xs text-gray-400">
                Configure phone settings to start receiving calls
              </p>
            </div>
          ) : (
            <div className="border border-gray-200 rounded-lg overflow-hidden">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-3 py-2 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">Caller</th>
                    <th className="px-3 py-2 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">Duration</th>
                    <th className="px-3 py-2 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">Status</th>
                    <th className="px-3 py-2 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">Started</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-100">
                  {calls.map((call) => {
                    const badge = STATUS_BADGE[call.status] ?? { label: call.status, className: 'bg-gray-100 text-gray-600' }
                    return (
                      <tr key={call.id} className="hover:bg-gray-50 cursor-pointer">
                        <td className="px-3 py-2">
                          <Link
                            href={`/agents/${agentName}/lens/calls/${call.id}`}
                            className="text-sm text-gray-900 font-medium hover:text-rose-600"
                          >
                            {call.caller_number || 'Unknown'}
                          </Link>
                        </td>
                        <td className="px-3 py-2">
                          <span className="text-sm text-gray-600 flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            {formatDuration(call.duration_seconds)}
                          </span>
                        </td>
                        <td className="px-3 py-2">
                          <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${badge.className}`}>
                            {badge.label}
                          </span>
                        </td>
                        <td className="px-3 py-2 text-sm text-gray-500">{formatDate(call.started_at)}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </AgentPagePanel>
    </AgentPageShell>
  )
}
