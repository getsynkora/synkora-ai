'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import { useParams } from 'next/navigation'
import {
  Swords,
  Users,
  Send,
  Clock,
  CheckCircle,
  AlertCircle,
  Loader2,
  UserPlus,
  MessageSquare,
} from 'lucide-react'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5001'

interface Participant {
  agent_name: string
  is_external: boolean
  color: string
}

interface DebateInfo {
  topic: string
  status: string
  rounds: number
  current_round: number
  participants: Participant[]
  verdict: string | null
}

interface RoundMessage {
  agent_name: string
  round: number
  content: string
  color?: string
}

interface RoundContext {
  debate_topic: string
  round: number
  total_rounds: number
  current_round: number
  status: string
  prior_messages: RoundMessage[]
  current_round_messages: RoundMessage[]
}

function getStatusBadge(status: string) {
  switch (status) {
    case 'pending':
      return (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-sand-deep px-2.5 py-0.5 text-xs font-medium text-gold ring-1 ring-inset ring-warn/20">
          <Clock className="h-3 w-3" />
          Pending
        </span>
      )
    case 'active':
      return (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-leaf-wash px-2.5 py-0.5 text-xs font-medium text-forest ring-1 ring-inset ring-leaf/20">
          <span className="h-1.5 w-1.5 rounded-full bg-leaf motion-safe:animate-pulse" />
          Live
        </span>
      )
    case 'synthesizing':
      return (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-sky-wash px-2.5 py-0.5 text-xs font-medium text-azure ring-1 ring-inset ring-azure/20">
          <Loader2 className="h-3 w-3 motion-safe:animate-spin" />
          Synthesizing
        </span>
      )
    case 'completed':
      return (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-cream px-2.5 py-0.5 text-xs font-medium text-ink-soft ring-1 ring-inset ring-ink-soft/20">
          <CheckCircle className="h-3 w-3" />
          Completed
        </span>
      )
    case 'error':
      return (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-blush-wash px-2.5 py-0.5 text-xs font-medium text-danger ring-1 ring-inset ring-danger/20">
          <AlertCircle className="h-3 w-3" />
          Error
        </span>
      )
    default:
      return (
        <span className="inline-flex items-center rounded-full bg-cream px-2.5 py-0.5 text-xs font-medium text-ink-soft ring-1 ring-inset ring-ink-soft/20">
          {status}
        </span>
      )
  }
}

export default function PublicJoinPage() {
  const params = useParams()
  const shareToken = params.id as string

  // Debate info
  const [debate, setDebate] = useState<DebateInfo | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Join state
  const [agentName, setAgentName] = useState('')
  const [participantId, setParticipantId] = useState<string | null>(null)
  const [participantToken, setParticipantToken] = useState<string | null>(null)
  const [joining, setJoining] = useState(false)

  // Round state
  const [roundContext, setRoundContext] = useState<RoundContext | null>(null)
  const [response, setResponse] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [respondedRounds, setRespondedRounds] = useState<Set<number>>(new Set())
  const [waitingMessage, setWaitingMessage] = useState<string | null>(null)

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Load debate info
  useEffect(() => {
    fetch(`${API_BASE}/api/v1/war-room/${shareToken}/public`)
      .then((r) => {
        if (!r.ok) throw new Error('Debate not found or is not publicly accessible.')
        return r.json()
      })
      .then((data) => setDebate(data))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [shareToken])

  // Poll for round context after joining
  const pollForRound = useCallback(async () => {
    if (!participantId || !debate) return

    try {
      // Refresh debate info
      const debateResp = await fetch(`${API_BASE}/api/v1/war-room/${shareToken}/public`)
      if (debateResp.ok) {
        const freshDebate = await debateResp.json()
        setDebate(freshDebate)

        if (freshDebate.status === 'completed') {
          setRoundContext(null)
          setWaitingMessage(null)
          if (pollRef.current) clearInterval(pollRef.current)
          return
        }

        if (freshDebate.status === 'error') {
          setRoundContext(null)
          setWaitingMessage(null)
          if (pollRef.current) clearInterval(pollRef.current)
          return
        }

        if (freshDebate.status === 'pending') {
          setWaitingMessage('Waiting for the debate to start…')
          return
        }
      }

      // Find the next round we need to respond to
      for (let r = 1; r <= debate.rounds; r++) {
        if (respondedRounds.has(r)) continue

        const resp = await fetch(`${API_BASE}/api/v1/war-room/${shareToken}/rounds/${r}`)
        if (!resp.ok) {
          // Round not available yet
          setWaitingMessage(`Waiting for Round ${r} to begin...`)
          setRoundContext(null)
          return
        }
        const ctx: RoundContext = await resp.json()

        if (ctx.status === 'completed' || ctx.status === 'error') {
          if (pollRef.current) clearInterval(pollRef.current)
          setRoundContext(null)
          setWaitingMessage(null)
          return
        }

        if (ctx.current_round >= r) {
          // Check if we already responded this round
          const alreadyResponded = ctx.current_round_messages.some(
            (m) => m.agent_name === agentName,
          )
          if (alreadyResponded) {
            setRespondedRounds((prev) => new Set([...prev, r]))
            continue
          }
          setRoundContext(ctx)
          setWaitingMessage(null)
          return
        }

        // Round hasn't started yet
        setWaitingMessage(`Waiting for Round ${r} to begin...`)
        setRoundContext(null)
        return
      }

      // All rounds responded to
      setWaitingMessage('All rounds submitted. Waiting for the debate to conclude…')
      setRoundContext(null)
    } catch {
      // Ignore polling errors silently
    }
  }, [participantId, debate, shareToken, respondedRounds, agentName])

  useEffect(() => {
    if (!participantId || !debate) return

    pollForRound()
    pollRef.current = setInterval(pollForRound, 4000)
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [participantId, debate, pollForRound])

  const handleJoin = async () => {
    if (!agentName.trim()) return
    setJoining(true)
    setError(null)
    try {
      const resp = await fetch(`${API_BASE}/api/v1/war-room/${shareToken}/join`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ agent_name: agentName.trim() }),
      })
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: 'Failed to join debate' }))
        throw new Error(err.detail || 'Failed to join debate')
      }
      const data = await resp.json()
      setParticipantId(data.participant_id)
      setParticipantToken(data.participant_token)
      // Refresh debate info to show new participant
      const debateResp = await fetch(`${API_BASE}/api/v1/war-room/${shareToken}/public`)
      if (debateResp.ok) setDebate(await debateResp.json())
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to join debate')
    } finally {
      setJoining(false)
    }
  }

  const handleSubmitResponse = async () => {
    if (!participantId || !roundContext || !response.trim()) return
    setSubmitting(true)
    setError(null)
    try {
      const resp = await fetch(`${API_BASE}/api/v1/war-room/${shareToken}/respond`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          participant_id: participantId,
          participant_token: participantToken,
          round: roundContext.round,
          content: response.trim(),
        }),
      })
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: 'Failed to submit response' }))
        throw new Error(err.detail || 'Failed to submit response')
      }
      setRespondedRounds((prev) => new Set([...prev, roundContext.round]))
      setResponse('')
      setRoundContext(null)
      setWaitingMessage('Response submitted! Waiting for the next round…')
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to submit response')
    } finally {
      setSubmitting(false)
    }
  }

  // --- Loading State ---
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-8 w-8 text-leaf motion-safe:animate-spin" />
          <p className="text-sm text-ink-mute">Loading debate…</p>
        </div>
      </div>
    )
  }

  // --- Error State (no debate loaded) ---
  if (!debate) {
    return (
      <div className="min-h-screen flex items-center justify-center p-4">
        <div className="bg-white rounded-lg border border-line shadow-sm p-8 max-w-md w-full text-center">
          <AlertCircle className="h-12 w-12 text-hotpink mx-auto mb-4" />
          <h2 className="text-lg font-semibold text-ink mb-2">Debate Not Found</h2>
          <p className="text-sm text-ink-mute">
            {error || 'This debate is not available or the link may have expired.'}
          </p>
        </div>
      </div>
    )
  }

  // --- Main Page ---
  return (
    <div className="min-h-screen">
      <div className="max-w-3xl mx-auto px-4 py-8 sm:py-12">
        {/* Header */}
        <div className="flex items-center gap-3 mb-8">
          <div className="flex items-center justify-center h-10 w-10 rounded-lg bg-ink text-white">
            <Swords className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-ink">AI War Room</h1>
            <p className="text-xs text-ink-mute">Public Debate Participation</p>
          </div>
        </div>

        {/* Debate Info Card */}
        <div className="bg-white rounded-lg border border-line shadow-sm p-6 mb-6">
          <div className="flex items-start justify-between gap-4 mb-4">
            <div className="flex-1 min-w-0">
              <h2 className="text-lg font-semibold text-ink mb-1">{debate.topic}</h2>
              <div className="flex items-center gap-3 text-sm text-ink-mute">
                <span className="flex items-center gap-1">
                  <Users className="h-3.5 w-3.5" />
                  {debate.participants.length} participant{debate.participants.length !== 1 ? 's' : ''}
                </span>
                <span className="flex items-center gap-1">
                  <MessageSquare className="h-3.5 w-3.5" />
                  Round {debate.current_round}/{debate.rounds}
                </span>
              </div>
            </div>
            {getStatusBadge(debate.status)}
          </div>

          {/* Participants */}
          <div className="flex flex-wrap gap-2">
            {debate.participants.map((p, i) => (
              <span
                key={i}
                className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset ring-line"
                style={{ backgroundColor: `${p.color}10`, color: p.color }}
              >
                <span
                  className="h-2 w-2 rounded-full"
                  style={{ backgroundColor: p.color }}
                />
                {p.agent_name}
                {p.is_external && (
                  <span className="text-[10px] text-ash font-normal">(external)</span>
                )}
              </span>
            ))}
          </div>
        </div>

        {/* Error Banner */}
        {error && (
          <div className="bg-blush-wash border border-blush rounded-lg p-4 mb-6 flex items-start gap-3">
            <AlertCircle className="h-5 w-5 text-leaf flex-shrink-0 mt-0.5" />
            <div className="flex-1 min-w-0">
              <p className="text-sm text-danger">{error}</p>
            </div>
            <button
              onClick={() => setError(null)}
              className="text-hotpink hover:text-danger text-sm"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Debate Completed State */}
        {debate.status === 'completed' && (
          <div className="bg-white rounded-lg border border-line shadow-sm p-8 text-center">
            <CheckCircle className="h-12 w-12 text-leaf mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-ink mb-2">Debate Completed</h3>
            <p className="text-sm text-ink-mute mb-4">
              This debate has concluded. Thank you for your participation.
            </p>
            {debate.verdict && (
              <div className="mt-4 p-4 bg-cream rounded-lg border border-line text-left">
                <h4 className="text-sm font-medium text-ink-soft mb-2">Verdict</h4>
                <p className="text-sm text-ink-soft whitespace-pre-wrap">{debate.verdict}</p>
              </div>
            )}
          </div>
        )}

        {/* Debate Error State */}
        {debate.status === 'error' && (
          <div className="bg-white rounded-lg border border-line shadow-sm p-8 text-center">
            <AlertCircle className="h-12 w-12 text-hotpink mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-ink mb-2">Debate Error</h3>
            <p className="text-sm text-ink-mute">
              This debate encountered an error and is no longer active.
            </p>
          </div>
        )}

        {/* Join Form (not yet joined, debate not completed/errored) */}
        {!participantId &&
          debate.status !== 'completed' &&
          debate.status !== 'error' && (
            <div className="bg-white rounded-lg border border-line shadow-sm p-6">
              <div className="flex items-center gap-2 mb-4">
                <UserPlus className="h-5 w-5 text-leaf" />
                <h3 className="text-base font-semibold text-ink">Join This Debate</h3>
              </div>
              <p className="text-sm text-ink-mute mb-4">
                Enter your agent name to participate as an external debater. Once joined, you will
                be able to submit responses each round.
              </p>
              <div className="flex gap-3">
                <input
                  type="text"
                  value={agentName}
                  onChange={(e) => setAgentName(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && agentName.trim() && !joining) handleJoin()
                  }}
                  placeholder="Your agent name…"
                  className="flex-1 rounded-lg border border-taupe px-4 py-2.5 text-sm text-ink placeholder-ash focus:border-hotpink focus:ring-2 focus:ring-hotpink/20 focus:outline-none transition"
                  disabled={joining}
                />
                <button
                  onClick={handleJoin}
                  disabled={!agentName.trim() || joining}
                  className="bg-ink text-white text-sm font-medium rounded-lg px-5 py-2.5 hover:from-danger hover:to-danger disabled:opacity-50 disabled:cursor-not-allowed transition flex items-center gap-2"
                >
                  {joining ? (
                    <>
                      <Loader2 className="h-4 w-4 motion-safe:animate-spin" />
                      Joining...
                    </>
                  ) : (
                    <>
                      <UserPlus className="h-4 w-4" />
                      Join Debate
                    </>
                  )}
                </button>
              </div>
            </div>
          )}

        {/* Post-Join: Waiting State */}
        {participantId && !roundContext && waitingMessage && debate.status !== 'completed' && debate.status !== 'error' && (
          <div className="bg-white rounded-lg border border-line shadow-sm p-8 text-center">
            <Loader2 className="h-8 w-8 text-leaf motion-safe:animate-spin mx-auto mb-4" />
            <h3 className="text-base font-semibold text-ink mb-1">{waitingMessage}</h3>
            <p className="text-sm text-ink-mute">
              This page will update automatically when it is your turn.
            </p>
          </div>
        )}

        {/* Post-Join: Active Round */}
        {participantId && roundContext && (
          <div className="space-y-6">
            {/* Round Header */}
            <div className="bg-white rounded-lg border border-line shadow-sm p-5">
              <div className="flex items-center justify-between mb-1">
                <h3 className="text-base font-semibold text-ink">
                  Round {roundContext.round} of {roundContext.total_rounds}
                </h3>
                <span className="inline-flex items-center gap-1.5 rounded-full bg-leaf-wash px-2.5 py-0.5 text-xs font-medium text-forest ring-1 ring-inset ring-leaf/20">
                  <span className="h-1.5 w-1.5 rounded-full bg-leaf motion-safe:animate-pulse" />
                  Your Turn
                </span>
              </div>
              <p className="text-sm text-ink-mute">
                Review the messages below and submit your response for this round.
              </p>
            </div>

            {/* Prior Round Messages */}
            {roundContext.prior_messages.length > 0 && (
              <div>
                <h4 className="text-xs font-medium text-ash mb-3">
                  Previous Rounds
                </h4>
                <div className="space-y-3">
                  {roundContext.prior_messages.map((msg, i) => (
                    <div
                      key={`prior-${i}`}
                      className="bg-white rounded-lg border border-line shadow-sm p-4"
                    >
                      <div className="flex items-center gap-2 mb-2">
                        <span
                          className="h-2.5 w-2.5 rounded-full"
                          style={{ backgroundColor: msg.color || '#6B7280' }}
                        />
                        <span className="text-sm font-medium text-ink">{msg.agent_name}</span>
                        <span className="text-xs text-ash">Round {msg.round}</span>
                      </div>
                      <p className="text-sm text-ink-soft whitespace-pre-wrap">{msg.content}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Current Round Messages (from other participants) */}
            {roundContext.current_round_messages.length > 0 && (
              <div>
                <h4 className="text-xs font-medium text-ash mb-3">
                  This Round
                </h4>
                <div className="space-y-3">
                  {roundContext.current_round_messages.map((msg, i) => (
                    <div
                      key={`current-${i}`}
                      className="bg-white rounded-lg border border-line shadow-sm p-4"
                    >
                      <div className="flex items-center gap-2 mb-2">
                        <span
                          className="h-2.5 w-2.5 rounded-full"
                          style={{ backgroundColor: msg.color || '#6B7280' }}
                        />
                        <span className="text-sm font-medium text-ink">{msg.agent_name}</span>
                        <span className="text-xs text-ash">Round {msg.round}</span>
                      </div>
                      <p className="text-sm text-ink-soft whitespace-pre-wrap">{msg.content}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Response Form */}
            <div className="bg-white rounded-lg border border-line shadow-sm p-5">
              <h4 className="text-sm font-medium text-ink mb-3">Your Response</h4>
              <textarea
                value={response}
                onChange={(e) => setResponse(e.target.value)}
                placeholder="Type your argument or response for this round…"
                rows={6}
                className="w-full rounded-lg border border-taupe px-4 py-3 text-sm text-ink placeholder-ash focus:border-hotpink focus:ring-2 focus:ring-hotpink/20 focus:outline-none transition resize-none"
                disabled={submitting}
              />
              <div className="flex items-center justify-between mt-3">
                <p className="text-xs text-ash">
                  {response.trim().length > 0
                    ? `${response.trim().length} characters`
                    : 'Write your response above'}
                </p>
                <button
                  onClick={handleSubmitResponse}
                  disabled={!response.trim() || submitting}
                  className="bg-ink text-white text-sm font-medium rounded-lg px-5 py-2.5 hover:from-danger hover:to-danger disabled:opacity-50 disabled:cursor-not-allowed transition flex items-center gap-2"
                >
                  {submitting ? (
                    <>
                      <Loader2 className="h-4 w-4 motion-safe:animate-spin" />
                      Submitting...
                    </>
                  ) : (
                    <>
                      <Send className="h-4 w-4" />
                      Submit Response
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Footer */}
        <div className="mt-8 text-center">
          <p className="text-xs text-ash">
            Powered by AI War Room
          </p>
        </div>
      </div>
    </div>
  )
}
