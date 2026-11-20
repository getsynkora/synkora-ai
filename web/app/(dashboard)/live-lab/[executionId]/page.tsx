'use client'

import { useEffect, useRef, useCallback } from 'react'
import { useParams } from 'next/navigation'
import { useLiveLabStore } from '@/lib/store/liveLabStore'
import { getExecution, getExecutionStreamUrl } from '@/lib/api/live-lab'
import type { ExecutionEvent } from '@/lib/api/live-lab'
import { secureStorage } from '@/lib/auth/secure-storage'
import { Activity, AlertTriangle } from 'lucide-react'
import { MetricsBar } from '@/components/live-lab/MetricsBar'
import { ActivityFeed } from '@/components/live-lab/ActivityFeed'
import { LiveWorkspace } from '@/components/live-lab/LiveWorkspace'
import { ExecutionPlan } from '@/components/live-lab/ExecutionPlan'
import DashboardPageShell, { DashboardPagePanel } from '@/components/dashboard/DashboardPageShell'

export default function ExecutionDetailPage() {
  const params = useParams()
  const executionId = params.executionId as string

  const {
    currentExecution,
    initCurrentExecution,
    clearCurrentExecution,
    appendEvent,
  } = useLiveLabStore()

  const abortRef = useRef<AbortController | null>(null)

  const startStream = useCallback(
    async (execId: string) => {
      const token = secureStorage.getAccessToken()
      const url = getExecutionStreamUrl(execId)

      abortRef.current = new AbortController()

      try {
        const response = await fetch(url, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
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
              const event: ExecutionEvent = JSON.parse(line.slice(6))
              if (event.type === 'stream_end') return
              appendEvent(event)
            } catch {
              // skip malformed events
            }
          }
        }
      } catch (err: unknown) {
        if (err instanceof DOMException && err.name === 'AbortError') return
        console.error('Stream error:', err)
      }
    },
    [appendEvent],
  )

  useEffect(() => {
    let cancelled = false

    async function load() {
      try {
        const exec = await getExecution(executionId)
        if (cancelled) return

        initCurrentExecution(exec)

        // Load stored events for completed executions
        if (exec.events && exec.events.length > 0) {
          for (const event of exec.events) {
            appendEvent(event)
          }
        }

        // If still running, start SSE stream for new events
        if (exec.status === 'running') {
          startStream(executionId)
        }
      } catch (err) {
        console.error('Failed to load execution:', err)
      }
    }

    load()

    return () => {
      cancelled = true
      abortRef.current?.abort()
      clearCurrentExecution()
    }
  }, [executionId, initCurrentExecution, clearCurrentExecution, appendEvent, startStream])

  if (!currentExecution) {
    return (
      <div className="dashboard-resource-page flex min-h-screen items-center justify-center">
        <div className="h-6 w-6 motion-safe:animate-spin rounded-full border-2 border-line border-t-ink" />
      </div>
    )
  }

  const isLive = currentExecution.status === 'running'
  const shortExecutionId = currentExecution.id.slice(0, 8)
  const statusLabel =
    currentExecution.status === 'running'
      ? 'Live'
      : currentExecution.status === 'complete'
        ? 'Completed'
        : currentExecution.status === 'error'
          ? 'Error'
          : 'Cancelled'

  return (
    <DashboardPageShell
      title={currentExecution.agentName}
      description={
        currentExecution.messagePreview ? (
          <>
            <span className="font-medium text-ink">&ldquo;{currentExecution.messagePreview}&rdquo;</span>
            <span className="text-ink-mute"> Live execution workspace, event timeline, and tool trace for this run.</span>
          </>
        ) : (
          'Live execution workspace, event timeline, and tool trace for this run.'
        )
      }
      icon={Activity}
      badge="Live Lab Session"
      maxWidthClassName="max-w-[1500px]"
      breadcrumbs={[
        { label: 'Home', href: '/' },
        { label: 'Live Lab', href: '/live-lab' },
        { label: currentExecution.agentName },
      ]}
      stats={[
        { label: 'Status', value: statusLabel },
        { label: 'Trigger', value: currentExecution.triggerSource },
        { label: 'Session', value: shortExecutionId },
      ]}
    >
      <DashboardPagePanel className="mb-6 overflow-hidden">
        <MetricsBar
          startedAt={currentExecution.metrics.startedAt}
          completedAt={currentExecution.metrics.completedAt || undefined}
          status={currentExecution.status}
          tokens={currentExecution.metrics.tokens}
          toolCount={currentExecution.metrics.toolCount}
          cost={currentExecution.metrics.cost}
          triggerSource={currentExecution.triggerSource}
          triggerDetail={currentExecution.triggerDetail || undefined}
          agentName={currentExecution.agentName}
          messagePreview={currentExecution.messagePreview}
        />
      </DashboardPagePanel>

      <DashboardPagePanel className="overflow-hidden p-3">
        <div className="grid min-h-[72vh] gap-3 xl:grid-cols-[280px_minmax(0,1fr)_260px]">
          <div className="hidden min-h-[24rem] overflow-hidden rounded-[1.6rem] border border-sand-deep bg-paper md:flex">
            <ActivityFeed events={currentExecution.events} isLive={isLive} />
          </div>

          <div className="min-h-[32rem] overflow-hidden rounded-[1.75rem] border border-sand-deep bg-white shadow-soft">
            <LiveWorkspace content={currentExecution.workspaceContent} isStreaming={isLive} />
          </div>

          <div className="hidden min-h-[24rem] overflow-hidden rounded-[1.6rem] border border-sand-deep bg-white xl:flex">
            <ExecutionPlan
              events={currentExecution.events}
              activeTools={currentExecution.activeTools}
              isLive={isLive}
            />
          </div>
        </div>
      </DashboardPagePanel>

      {currentExecution.status === 'error' && currentExecution.error ? (
        <DashboardPagePanel className="mt-6 border-blush-wash bg-cream p-4">
          <div className="flex items-start gap-3">
            <div className="rounded-[1rem] bg-blush-wash p-2 text-wine">
              <AlertTriangle className="h-4 w-4" />
            </div>
            <div>
              <p className="text-sm font-semibold text-wine">Execution error</p>
              <p className="mt-1 text-sm leading-6 text-wine">{currentExecution.error}</p>
            </div>
          </div>
        </DashboardPagePanel>
      ) : null}
    </DashboardPageShell>
  )
}
