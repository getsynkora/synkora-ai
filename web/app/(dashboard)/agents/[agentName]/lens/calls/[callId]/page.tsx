'use client'

import { useState, useEffect } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import { ArrowLeft, Phone, Clock, User, Bot, ExternalLink } from 'lucide-react'
import { getPhoneCall, type PhoneCall } from '@/lib/api/phone'
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

export default function CallDetailPage() {
  const params = useParams()
  const agentName = params.agentName as string
  const callId = params.callId as string

  const [call, setCall] = useState<PhoneCall | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getPhoneCall(callId)
      .then(setCall)
      .catch(() => setError('Call not found'))
      .finally(() => setLoading(false))
  }, [callId])

  return (
    <AgentPageShell agentName={agentName} title="Call Detail" icon={Phone}>
      <AgentPagePanel>
        <div className="space-y-6">
          {/* Back link */}
          <Link
            href={`/agents/${agentName}/lens/calls`}
            className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to calls
          </Link>

          {loading ? (
            <div className="flex items-center justify-center h-32 text-gray-400 text-sm">Loading…</div>
          ) : error || !call ? (
            <div className="text-sm text-gray-500">{error || 'Call not found'}</div>
          ) : (
            <>
              {/* Call metadata card */}
              <div className="border border-gray-200 rounded-lg p-4 space-y-3">
                <div className="flex items-center gap-2">
                  <Phone className="w-4 h-4 text-gray-500" />
                  <h2 className="text-base font-semibold text-gray-900">
                    {call.caller_number || 'Unknown caller'}
                  </h2>
                  {STATUS_BADGE[call.status] && (
                    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${STATUS_BADGE[call.status].className}`}>
                      {STATUS_BADGE[call.status].label}
                    </span>
                  )}
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
                  <div>
                    <p className="text-xs text-gray-500">Started</p>
                    <p className="text-gray-700 font-medium">{formatDate(call.started_at)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">Duration</p>
                    <p className="text-gray-700 font-medium flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {formatDuration(call.duration_seconds)}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">Provider</p>
                    <p className="text-gray-700 font-medium capitalize">{call.provider}</p>
                  </div>
                  {call.recording_url && (
                    <div>
                      <p className="text-xs text-gray-500">Recording</p>
                      <a
                        href={call.recording_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-rose-600 hover:underline flex items-center gap-1 font-medium"
                      >
                        Listen <ExternalLink className="w-3 h-3" />
                      </a>
                    </div>
                  )}
                </div>
              </div>

              {/* Transcript */}
              {call.messages && call.messages.length > 0 ? (
                <div className="space-y-3">
                  <h3 className="text-sm font-semibold text-gray-700">Transcript</h3>
                  <div className="space-y-2">
                    {call.messages.map((msg, i) => (
                      <div
                        key={i}
                        className={`flex gap-3 ${msg.role === 'user' ? '' : 'flex-row-reverse'}`}
                      >
                        <div className={`flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center ${
                          msg.role === 'user' ? 'bg-gray-100' : 'bg-rose-50'
                        }`}>
                          {msg.role === 'user'
                            ? <User className="w-3.5 h-3.5 text-gray-500" />
                            : <Bot className="w-3.5 h-3.5 text-rose-500" />
                          }
                        </div>
                        <div className={`max-w-[75%] px-3 py-2 rounded-xl text-sm ${
                          msg.role === 'user'
                            ? 'bg-gray-100 text-gray-800'
                            : 'bg-rose-50 text-gray-800'
                        }`}>
                          {msg.content}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="text-sm text-gray-400 italic">No transcript available for this call.</div>
              )}
            </>
          )}
        </div>
      </AgentPagePanel>
    </AgentPageShell>
  )
}
