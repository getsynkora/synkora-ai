'use client'

import { useEffect, useCallback, useRef, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import toast from 'react-hot-toast'
import { getLifeAudit, getLifeAuditStreamUrl } from '@/lib/api/rate-my-life'
import { getDebate } from '@/lib/api/war-room'
import type { DebateEvent } from '@/lib/api/war-room'
import { useWarRoomStore } from '@/lib/store/warRoomStore'
import { secureStorage } from '@/lib/auth/secure-storage'
import { LifeDebateArena } from '@/components/rate-my-life/LifeDebateArena'
import { LifeScorecard } from '@/components/rate-my-life/LifeScorecard'
import type { LifeAuditResult } from '@/lib/api/rate-my-life'
import { cn } from '@/lib/utils/cn'
import { Sparkles, Scale, Share2, Activity } from 'lucide-react'
import DashboardPageShell, { DashboardPagePanel, DashboardPageTabs } from '@/components/dashboard/DashboardPageShell'

type ViewMode = 'debate' | 'scorecard'

export default function LifeAuditResultPage() {
  const params = useParams()
  const router = useRouter()
  const auditId = params.id as string
  const abortRef = useRef<AbortController | null>(null)

  const [viewMode, setViewMode] = useState<ViewMode>('debate')
  const [auditResult, setAuditResult] = useState<LifeAuditResult | null>(null)

  const { currentDebate, streamingParticipantId, streamingContent, setDebate, clearDebate, handleEvent } =
    useWarRoomStore()

  // Start the debate SSE stream
  const startStream = useCallback(async () => {
    const token = secureStorage.getAccessToken()
    const url = getLifeAuditStreamUrl(auditId)
    abortRef.current = new AbortController()

    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        signal: abortRef.current.signal,
      })

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
            // skip malformed events
          }
        }
      }

      // Stream completed -- fetch the parsed scores
      const result = await getLifeAudit(auditId)
      setAuditResult(result)
      setViewMode('scorecard')
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === 'AbortError') return
      console.error('Life audit stream error:', err)
    }
  }, [auditId, handleEvent])

  // Load the debate session on mount
  useEffect(() => {
    async function load() {
      try {
        // Load as a debate session (it IS a DebateSession)
        const debate = await getDebate(auditId)
        setDebate(debate)

        if (debate.status === 'completed') {
          // Already completed -- load scorecard directly
          const result = await getLifeAudit(auditId)
          setAuditResult(result)
          setViewMode('scorecard')
        } else if (debate.status === 'pending') {
          // Auto-start the debate
          startStream()
        }
      } catch (err) {
        console.error('Failed to load life audit:', err)
        router.push('/rate-my-life')
      }
    }
    load()
    return () => {
      abortRef.current?.abort()
      clearDebate()
    }
  }, [auditId, setDebate, clearDebate, router, startStream])

  if (!currentDebate) {
    return (
      <div className="dashboard-resource-page flex min-h-screen items-center justify-center">
        <div className="text-center">
          <div className="mx-auto mb-3 h-8 w-8 animate-spin rounded-full border-2 border-gray-200 border-t-[#171717]" />
          <p className="text-sm text-gray-500">Loading your life audit...</p>
        </div>
      </div>
    )
  }

  const isLive = currentDebate.status === 'active' || currentDebate.status === 'synthesizing'
  const isCompleted = currentDebate.status === 'completed'

  return (
    <DashboardPageShell
      title="Rate My Life"
      description="Watch specialist AI agents debate your answers in real time, then review the final scorecard and verdict."
      icon={Sparkles}
      badge="Labs"
      maxWidthClassName="max-w-6xl"
      breadcrumbs={[
        { label: 'Home', href: '/' },
        { label: 'Rate My Life', href: '/rate-my-life' },
        { label: auditId },
      ]}
      stats={[
        { label: 'Status', value: isLive ? 'Live debate' : isCompleted ? 'Completed' : 'Starting' },
        { label: 'Agents', value: currentDebate.participants.length },
        { label: 'Round', value: `${currentDebate.current_round}/${currentDebate.rounds}` },
      ]}
      actions={
        <div className="flex flex-wrap items-center gap-3">
          {isCompleted && auditResult ? (
            <DashboardPageTabs
              activeId={viewMode}
              onChange={(id) => setViewMode(id as ViewMode)}
              items={[
                { id: 'scorecard', label: 'Scorecard', icon: <Scale className="h-4 w-4" /> },
                { id: 'debate', label: 'Debate', icon: <Activity className="h-4 w-4" /> },
              ]}
              className="inline-flex"
            />
          ) : null}

          {currentDebate.share_token && isCompleted ? (
            <button
              onClick={() => {
                const url = `${window.location.origin}/war-room/${currentDebate.share_token}/live`
                navigator.clipboard.writeText(url)
                toast.success('Share link copied')
              }}
              className="inline-flex items-center gap-2 rounded-[1rem] border border-black/10 bg-white/85 px-4 py-3 text-sm font-semibold text-gray-700 transition-colors hover:bg-white hover:text-[#171717]"
            >
              <Share2 className="h-4 w-4" />
              Share
            </button>
          ) : null}
        </div>
      }
    >
      {!isLive ? (
        <DashboardPagePanel className="mb-6 p-4">
          <div className="flex flex-wrap items-center gap-2">
            {currentDebate.participants.map((p) => (
              <span
                key={p.id}
                className="inline-flex flex-shrink-0 items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium text-gray-700"
                style={{ backgroundColor: `${p.color}10`, borderColor: `${p.color}30` }}
              >
                <span className="h-2 w-2 rounded-full" style={{ backgroundColor: p.color }} />
                {p.agent_name}
              </span>
            ))}
          </div>
        </DashboardPagePanel>
      ) : null}

      {viewMode === 'scorecard' && auditResult ? (
        <div className="overflow-y-auto">
          <div className="mx-auto max-w-4xl py-1">
            <LifeScorecard
              scores={auditResult.scores}
              highlights={auditResult.agent_highlights}
              verdict={auditResult.verdict}
              shareToken={currentDebate.share_token}
            />
          </div>
        </div>
      ) : (
        <DashboardPagePanel className="overflow-hidden">
          <LifeDebateArena
            messages={currentDebate.messages}
            participants={currentDebate.participants}
            streamingParticipantId={streamingParticipantId}
            streamingContent={streamingContent}
            verdict={currentDebate.verdict}
            currentRound={currentDebate.current_round}
            totalRounds={currentDebate.rounds}
          />
        </DashboardPagePanel>
      )}
    </DashboardPageShell>
  )
}
