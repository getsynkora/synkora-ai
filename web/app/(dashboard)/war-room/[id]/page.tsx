'use client'

import { useEffect, useCallback, useRef, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import toast from 'react-hot-toast'
import { getDebate, getDebateStartStreamUrl, stopDebate } from '@/lib/api/war-room'
import type { DebateEvent } from '@/lib/api/war-room'
import { useWarRoomStore } from '@/lib/store/warRoomStore'
import { secureStorage } from '@/lib/auth/secure-storage'
import { DebateArena } from '@/components/war-room/DebateArena'
import { Swords, GitPullRequest, ExternalLink, PlugZap, Share2 } from 'lucide-react'
import { ConnectAgentModal } from '@/components/war-room/ConnectAgentModal'
import { cn } from '@/lib/utils/cn'
import DashboardPageShell, { DashboardPagePanel } from '@/components/dashboard/DashboardPageShell'

const STATUS_CONFIG: Record<string, { label: string; color: string }> = {
  pending: { label: 'Ready to Start', color: 'text-gray-500' },
  active: { label: 'Live', color: 'text-green-600' },
  synthesizing: { label: 'Synthesizing Verdict...', color: 'text-amber-600' },
  completed: { label: 'Completed', color: 'text-blue-600' },
  error: { label: 'Error', color: 'text-red-600' },
}

export default function DebateSessionPage() {
  const params = useParams()
  const router = useRouter()
  const debateId = params.id as string
  const abortRef = useRef<AbortController | null>(null)
  const [showConnectModal, setShowConnectModal] = useState(false)

  const { currentDebate, streamingParticipantId, streamingContent, setDebate, clearDebate, handleEvent } =
    useWarRoomStore()

  const startStream = useCallback(async () => {
    const token = secureStorage.getAccessToken()
    const url = getDebateStartStreamUrl(debateId)
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
            // skip
          }
        }
      }
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === 'AbortError') return
      console.error('Debate stream error:', err)
    }
  }, [debateId, handleEvent])

  useEffect(() => {
    async function load() {
      try {
        const debate = await getDebate(debateId)
        setDebate(debate)
      } catch (err) {
        console.error('Failed to load debate:', err)
        router.push('/war-room')
      }
    }
    load()
    return () => {
      abortRef.current?.abort()
      clearDebate()
    }
  }, [debateId, setDebate, clearDebate, router])

  if (!currentDebate) {
    return (
      <div className="dashboard-resource-page flex min-h-screen items-center justify-center">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-gray-200 border-t-[#171717]" />
      </div>
    )
  }

  const statusInfo = STATUS_CONFIG[currentDebate.status] || STATUS_CONFIG.pending
  const canStart = currentDebate.status === 'pending' || currentDebate.status === 'error'
  const isLive = currentDebate.status === 'active' || currentDebate.status === 'synthesizing'

  return (
    <DashboardPageShell
      title={currentDebate.topic}
      description="Run a live multi-agent debate, monitor status in real time, and share the session externally when needed."
      icon={Swords}
      badge="War Room"
      maxWidthClassName="max-w-6xl"
      breadcrumbs={[
        { label: 'Home', href: '/' },
        { label: 'War Room', href: '/war-room' },
        { label: currentDebate.topic },
      ]}
      stats={[
        { label: 'Status', value: statusInfo.label },
        { label: 'Agents', value: currentDebate.participants.length },
        { label: 'Round', value: `${currentDebate.current_round}/${currentDebate.rounds}` },
      ]}
      actions={
        <>
          {canStart ? (
            <button
              onClick={() => router.push(`/war-room/create?edit=${debateId}`)}
              className="inline-flex items-center gap-2 rounded-[1rem] border border-black/10 bg-white/85 px-4 py-3 text-sm font-semibold text-gray-700 transition-colors hover:bg-white hover:text-[#171717]"
            >
              Edit
            </button>
          ) : null}
          {currentDebate.allow_external && currentDebate.share_token ? (
            <button
              onClick={() => setShowConnectModal(true)}
              className="inline-flex items-center gap-2 rounded-[1rem] border border-[#f0d8bf] bg-[#fff5e7] px-4 py-3 text-sm font-semibold text-[#9d6a1d] transition-colors hover:bg-[#fef0da]"
            >
              <PlugZap className="h-4 w-4" />
              Connect Agent
            </button>
          ) : null}
          {currentDebate.share_token ? (
            <button
              onClick={() => {
                const url = `${window.location.origin}/war-room/${currentDebate.share_token}/live`
                navigator.clipboard.writeText(url)
                toast.success('Share link copied')
              }}
              className="inline-flex items-center gap-2 rounded-[1rem] border border-black/10 bg-white/85 px-4 py-3 text-sm font-semibold text-gray-700 transition-colors hover:bg-white hover:text-[#171717]"
            >
              <Share2 className="h-4 w-4" />
              Copy Share Link
            </button>
          ) : null}
          {isLive ? (
            <button
              onClick={async () => {
                try {
                  abortRef.current?.abort()
                  const updated = await stopDebate(debateId)
                  setDebate(updated)
                } catch (err) {
                  console.error('Failed to stop debate:', err)
                }
              }}
              className="inline-flex items-center gap-2 rounded-[1rem] border border-[#eed6dd] bg-[#fdf3f5] px-4 py-3 text-sm font-semibold text-[#8a445c] transition-colors hover:bg-[#f9e9ed]"
            >
              Stop Debate
            </button>
          ) : null}
          {canStart ? (
            <button
              onClick={startStream}
              className="inline-flex items-center gap-2 rounded-[1rem] bg-[#171717] px-4 py-3 text-sm font-semibold text-white transition-colors hover:bg-black"
            >
              Start Debate
            </button>
          ) : null}
        </>
      }
    >
      {currentDebate.debate_metadata?.context?.type === 'github_pr' ? (
        <DashboardPagePanel className="mb-6 p-4">
          <div className="flex flex-wrap items-center gap-3">
            <div className="rounded-[0.9rem] bg-[#edf7f1] p-2">
              <GitPullRequest className="h-4 w-4 text-[#2d8b69]" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold text-gray-900">
                {currentDebate.debate_metadata.context.pr_title}
              </p>
              <p className="text-xs text-gray-500">
                {currentDebate.debate_metadata.context.repo_full_name}#{currentDebate.debate_metadata.context.pr_number}
              </p>
            </div>
            {currentDebate.debate_metadata.context.github_url ? (
              <a
                href={currentDebate.debate_metadata.context.github_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 rounded-[0.9rem] border border-black/10 bg-white/90 px-3 py-2 text-xs font-semibold text-gray-700 transition-colors hover:bg-white hover:text-[#171717]"
              >
                Open PR
                <ExternalLink className="h-3.5 w-3.5" />
              </a>
            ) : null}
          </div>
        </DashboardPagePanel>
      ) : null}

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
              {p.role ? <span className="text-gray-500">({p.role})</span> : null}
              {p.is_external ? <span className="text-[#b84a3a] text-[10px]">EXT</span> : null}
            </span>
          ))}
        </div>
      </DashboardPagePanel>

      <DashboardPagePanel className="overflow-hidden">
        <DebateArena
          messages={currentDebate.messages}
          participants={currentDebate.participants}
          streamingParticipantId={streamingParticipantId}
          streamingContent={streamingContent}
          verdict={currentDebate.verdict}
        />
      </DashboardPagePanel>

      {/* Connect Agent Modal */}
      {currentDebate.share_token && (
        <ConnectAgentModal
          isOpen={showConnectModal}
          onClose={() => setShowConnectModal(false)}
          shareToken={currentDebate.share_token}
          topic={currentDebate.topic}
        />
      )}
    </DashboardPageShell>
  )
}
