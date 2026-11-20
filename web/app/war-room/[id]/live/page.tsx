'use client'

import { useEffect, useState, useMemo, useRef } from 'react'
import { useParams } from 'next/navigation'
import { getPublicDebate, getPublicDebateStreamUrl } from '@/lib/api/war-room'
import type { DebateSession, DebateMessage, DebateEvent } from '@/lib/api/war-room'
import { DebateArena } from '@/components/war-room/DebateArena'
import { LifeScorecard } from '@/components/rate-my-life/LifeScorecard'
import type { LifeAuditScores, AgentHighlight } from '@/lib/api/rate-my-life'

// ── Client-side score parsing (mirrors backend SCORE_PATTERN) ────────────────

const SCORE_RE = /\[SCORES?\]\s*Career:\s*(\d+),?\s*Financial:\s*(\d+),?\s*Physical:\s*(\d+),?\s*Mental:\s*(\d+),?\s*Relationships:\s*(\d+),?\s*Growth:\s*(\d+)(?:,?\s*Overall:\s*(\d+))?/i

function parseScoresFromContent(content: string): Record<string, number> | null {
  const m = SCORE_RE.exec(content)
  if (!m) return null
  const clamp = (v: number) => Math.max(1, Math.min(10, v))
  const scores: Record<string, number> = {
    career: clamp(parseInt(m[1])),
    financial: clamp(parseInt(m[2])),
    physical: clamp(parseInt(m[3])),
    mental: clamp(parseInt(m[4])),
    relationships: clamp(parseInt(m[5])),
    growth: clamp(parseInt(m[6])),
  }
  if (m[7]) scores.overall = clamp(parseInt(m[7]))
  return scores
}

function extractHighlightQuote(content: string): string {
  const cleaned = content.replace(/\[SCORES?\][\s\S]*/i, '').trim()
  const sentences = cleaned.split(/(?<=[.!?])\s+/)
  return sentences.slice(0, 2).join(' ').slice(0, 200)
}

const DIM_LABELS: Record<string, string> = {
  career: 'Career & Growth',
  financial: 'Financial Health',
  physical: 'Physical Health',
  mental: 'Mental Wellbeing',
  relationships: 'Relationships',
  growth: 'Personal Growth',
}

function buildAuditFromDebate(debate: DebateSession): {
  scores: LifeAuditScores
  highlights: AgentHighlight[]
} | null {
  const messages = debate.messages || []
  const allScores: Record<string, number>[] = []
  const highlights: AgentHighlight[] = []
  const dims = Object.keys(DIM_LABELS)

  for (const msg of messages) {
    if (msg.is_verdict) continue
    const scores = parseScoresFromContent(msg.content)
    if (!scores) continue
    allScores.push(scores)
    const bestDim = dims.reduce((a, b) => (scores[a] || 0) >= (scores[b] || 0) ? a : b)
    highlights.push({
      agent_name: msg.agent_name,
      dimension: DIM_LABELS[bestDim] || bestDim,
      quote: extractHighlightQuote(msg.content),
      score: scores[bestDim] || 0,
    })
  }

  if (allScores.length === 0) return null

  // Prefer synthesizer scores from verdict
  const verdictScores = debate.verdict ? parseScoresFromContent(debate.verdict) : null

  const final: LifeAuditScores = {
    career: 0, financial: 0, physical: 0, mental: 0, relationships: 0, growth: 0, overall: 0,
  }

  if (verdictScores) {
    for (const d of dims) {
      (final as any)[d] = verdictScores[d] || 0
    }
    final.overall = verdictScores.overall || Math.round(dims.reduce((sum, d) => sum + ((final as any)[d] || 0), 0) / 6 * 10) / 10
  } else {
    for (const d of dims) {
      (final as any)[d] = Math.round(allScores.reduce((sum, s) => sum + (s[d] || 0), 0) / allScores.length * 10) / 10
    }
    final.overall = Math.round(dims.reduce((sum, d) => sum + ((final as any)[d] || 0), 0) / 6 * 10) / 10
  }

  return { scores: final, highlights }
}

// ── Main Page ────────────────────────────────────────────────────────────────

export default function PublicDebatePage() {
  const params = useParams()
  const shareToken = params.id as string

  const [debate, setDebate] = useState<DebateSession | null>(null)
  const [error, setError] = useState('')
  const [streamingParticipantId, setStreamingParticipantId] = useState<string | null>(null)
  const [streamingContent, setStreamingContent] = useState('')

  const abortRef = useRef<AbortController | null>(null)

  const isLifeAudit = useMemo(() => {
    if (!debate?.debate_metadata) return false
    const meta = debate.debate_metadata as Record<string, unknown>
    return meta.type === 'life-audit'
  }, [debate])

  const auditData = useMemo(() => {
    if (!debate || !isLifeAudit || debate.status !== 'completed') return null
    return buildAuditFromDebate(debate)
  }, [debate, isLifeAudit])

  useEffect(() => {
    async function load() {
      try {
        const data = await getPublicDebate(shareToken)
        setDebate(data)

        if (data.status === 'active' || data.status === 'synthesizing') {
          startLiveStream()
        }
      } catch {
        setError('This debate is not available or is no longer public.')
      }
    }

    async function startLiveStream() {
      const url = getPublicDebateStreamUrl(shareToken)
      abortRef.current = new AbortController()

      try {
        const response = await fetch(url, { signal: abortRef.current.signal })
        if (!response.ok || !response.body) return

        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() ?? ''

          for (const line of lines) {
            if (!line.trim() || !line.startsWith('data: ')) continue
            try {
              const event: DebateEvent = JSON.parse(line.slice(6))
              handleEvent(event)
            } catch {
              // skip
            }
          }
        }
      } catch (err: unknown) {
        if (err instanceof DOMException && err.name === 'AbortError') return
      }
    }

    function handleEvent(event: DebateEvent) {
      if (event.type === 'message') {
        setDebate((prev) => {
          if (!prev) return prev
          const msg = event as unknown as DebateMessage
          return { ...prev, messages: [...prev.messages, msg] }
        })
      }
      if (event.type === 'verdict') {
        setDebate((prev) => prev ? { ...prev, verdict: event.content || '', status: 'completed' } : prev)
      }
      if (event.type === 'debate_end') {
        setDebate((prev) => prev ? { ...prev, status: 'completed' } : prev)
      }
    }

    load()
    return () => { abortRef.current?.abort() }
  }, [shareToken])

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="w-14 h-14 rounded-2xl bg-sand-deep flex items-center justify-center mx-auto mb-4">
            <svg aria-hidden="true" className="w-7 h-7 text-hotpink" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
            </svg>
          </div>
          <h2 className="text-xl font-bold text-ink mb-2">Not Available</h2>
          <p className="text-sm text-ink-mute max-w-xs mx-auto">{error}</p>
        </div>
      </div>
    )
  }

  if (!debate) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-line border-t-brand rounded-full motion-safe:animate-spin" />
      </div>
    )
  }

  // ── Life Audit completed: show scorecard ──
  if (isLifeAudit && auditData && debate.status === 'completed') {
    return (
      <div className="min-h-screen">
        {/* Header */}
        <div className="border-b border-line bg-white/80">
          <div className="max-w-4xl mx-auto px-4 py-5">
            <div className="flex items-center justify-between">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-blush-wash text-leaf text-xs font-bold">
                    <svg aria-hidden="true" className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                    </svg>
                    AI Life Audit
                  </div>
                  <span className="text-xs font-medium text-azure bg-sky-wash px-2 py-0.5 rounded-full">Completed</span>
                </div>
                <h1 className="text-xl font-bold text-ink">Rate My Life</h1>
                <p className="text-sm text-ink-mute mt-0.5">
                  {debate.participants.length} specialist agents | {debate.rounds} debate rounds
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Scorecard */}
        <div className="max-w-4xl mx-auto px-4 py-8">
          <LifeScorecard
            scores={auditData.scores}
            highlights={auditData.highlights}
            verdict={debate.verdict}
          />
        </div>
      </div>
    )
  }

  // ── Regular debate or in-progress life audit ──
  return (
    <div className="h-screen bg-cream flex flex-col overflow-hidden">
      {/* Public header */}
      <div className="border-b border-line bg-white/80 px-4 py-4">
        <div className="max-w-3xl mx-auto">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl font-bold text-ink">{debate.topic}</h1>
              <div className="flex items-center gap-3 mt-1.5">
                <span className="text-sm text-ink-mute font-medium">{debate.participants.length} agents</span>
                <span className="text-sm text-ink-mute font-medium">Round {debate.current_round}/{debate.rounds}</span>
                {(debate.status === 'active' || debate.status === 'synthesizing') && (
                  <span className="flex items-center gap-1.5 text-sm text-leaf font-semibold">
                    <span className="w-2 h-2 rounded-full bg-leaf motion-safe:animate-pulse" />
                    Live
                  </span>
                )}
                {debate.status === 'completed' && (
                  <span className="text-sm text-azure font-semibold">Completed</span>
                )}
              </div>
            </div>
            {isLifeAudit && (
              <div className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-blush-wash text-leaf text-xs font-bold">
                <svg aria-hidden="true" className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
                AI Life Audit
              </div>
            )}
          </div>

          {/* Participant pills */}
          <div className="flex items-center gap-2 mt-3 overflow-x-auto pb-1">
            {debate.participants.map((p) => (
              <span
                key={p.id}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold text-ink-soft border flex-shrink-0"
                style={{ backgroundColor: `${p.color}12`, borderColor: `${p.color}30` }}
              >
                <span className="w-2 h-2 rounded-full" style={{ backgroundColor: p.color }} />
                {p.agent_name}
              </span>
            ))}
          </div>
        </div>
      </div>

      <DebateArena
        messages={debate.messages}
        participants={debate.participants}
        streamingParticipantId={streamingParticipantId}
        streamingContent={streamingContent}
        verdict={debate.verdict}
      />
    </div>
  )
}
