'use client'

import { useState, useEffect } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import { ArrowLeft, Phone, Clock, User, Bot, ExternalLink } from 'lucide-react'
import { getPhoneCall, type PhoneCall } from '@/lib/api/phone'
import AgentPageShell, { AgentPagePanel } from '@/components/agents/AgentPageShell'

const STATUS_BADGE: Record<string, { label: string; className: string }> = {
  completed: { label: 'Completed', className: 'bg-leaf-wash text-forest' },
  active: { label: 'Active', className: 'bg-sky-wash text-azure' },
  ringing: { label: 'Ringing', className: 'bg-sand-deep text-gold' },
  failed: { label: 'Failed', className: 'bg-blush-wash text-danger' },
  no_answer: { label: 'No Answer', className: 'bg-sand text-ink-soft' },
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
            className="inline-flex items-center gap-1 text-sm text-ink-mute hover:text-ink-soft"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to calls
          </Link>

          {loading ? (
            <div className="flex items-center justify-center h-32 text-ash text-sm">Loading…</div>
          ) : error || !call ? (
            <div className="text-sm text-ink-mute">{error || 'Call not found'}</div>
          ) : (
            <>
              {/* Call metadata card */}
              <div className="border border-line rounded-lg p-4 space-y-3">
                <div className="flex items-center gap-2">
                  <Phone className="w-4 h-4 text-ink-mute" />
                  <h2 className="text-base font-semibold text-ink">
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
                    <p className="text-xs text-ink-mute">Started</p>
                    <p className="text-ink-soft font-medium">{formatDate(call.started_at)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-ink-mute">Duration</p>
                    <p className="text-ink-soft font-medium flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {formatDuration(call.duration_seconds)}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-ink-mute">Provider</p>
                    <p className="text-ink-soft font-medium capitalize">{call.provider}</p>
                  </div>
                  {call.recording_url && (
                    <div>
                      <p className="text-xs text-ink-mute">Recording</p>
                      <a
                        href={call.recording_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-leaf hover:underline flex items-center gap-1 font-medium"
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
                  <h3 className="text-sm font-semibold text-ink-soft">Transcript</h3>
                  <div className="space-y-2">
                    {call.messages.map((msg, i) => (
                      <div
                        key={i}
                        className={`flex gap-3 ${msg.role === 'user' ? '' : 'flex-row-reverse'}`}
                      >
                        <div className={`flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center ${
                          msg.role === 'user' ? 'bg-sand' : 'bg-blush-wash'
                        }`}>
                          {msg.role === 'user'
                            ? <User className="w-3.5 h-3.5 text-ink-mute" />
                            : <Bot className="w-3.5 h-3.5 text-leaf" />
                          }
                        </div>
                        <div className={`max-w-[75%] px-3 py-2 rounded-xl text-sm ${
                          msg.role === 'user'
                            ? 'bg-sand text-ink'
                            : 'bg-blush-wash text-ink'
                        }`}>
                          {msg.content}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="text-sm text-ash italic">No transcript available for this call.</div>
              )}
            </>
          )}
        </div>
      </AgentPagePanel>
    </AgentPageShell>
  )
}
